"""Jednokierunkowa synchronizacja przezbrojeń z Oracle do PostgreSQL."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime

import oracledb
import psycopg2


LOGGER = logging.getLogger("synch_przezbrojenia")
SYNC_USER = "oracle_sync"

ORACLE_QUERY = r"""
SELECT
    zk.numer_zamowienia_wg_klienta,
    zk.POTWIERDZENIE_ZAMOWIENIA,
    zk.DATA_WPROWADZENIA,
    zk.DATA_ZATWIERDZENIA,
    zk.TERMIN_KLIENTA,
    SUBSTR(
        zk.numer_zamowienia_wg_klienta,
        1,
        INSTR(zk.numer_zamowienia_wg_klienta, ' ') - 1
    ) AS obecna_wersja,
    CASE
        WHEN INSTR(zk.numer_zamowienia_wg_klienta, ' na ', 1, 1) > 0 THEN
            SUBSTR(
                zk.numer_zamowienia_wg_klienta,
                INSTR(zk.numer_zamowienia_wg_klienta, ' na ', 1, 1) + LENGTH(' na '),
                INSTR(
                    zk.numer_zamowienia_wg_klienta || ' ',
                    ' ',
                    INSTR(zk.numer_zamowienia_wg_klienta, ' na ', 1, 1)
                        + LENGTH(' na ') + 1
                ) - (
                    INSTR(zk.numer_zamowienia_wg_klienta, ' na ', 1, 1)
                        + LENGTH(' na ')
                )
            )
        ELSE NULL
    END AS nastepna_wersja,
    CASE
        WHEN REGEXP_LIKE(
            SUBSTR(zk.numer_zamowienia_wg_klienta, -16),
            '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$'
        ) THEN
            TO_DATE(
                SUBSTR(zk.numer_zamowienia_wg_klienta, -16),
                'YYYY-MM-DD HH24:MI'
            )
        ELSE NULL
    END AS termin_przezbr
FROM ZAMOWIENIA_KLIENTOW zk
WHERE zk.KOD_RODZAJU_ZAMOWIENIA = 'ZSZF'
ORDER BY zk.DATA_ZATWIERDZENIA DESC
"""


@dataclass(frozen=True)
class OracleChangeover:
    order_number: str
    available_date: datetime
    from_mould_number: str
    to_mould_number: str
    needed_date: datetime


@dataclass
class SyncResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_invalid: int = 0
    skipped_missing_mould: int = 0


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Brak wymaganej zmiennej środowiskowej: {name}")
    return value


def oracle_connection():
    return oracledb.connect(
        user=required_env("ORACLE_USER"),
        password=required_env("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN", "10.1.1.26/lamela"),
    )


def postgres_connection():
    return psycopg2.connect(
        user=os.getenv("PGUSER", "postgres"),
        password=required_env("PGPASSWORD"),
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "5432"),
        database=os.getenv("PGDATABASE", "mouldbase"),
    )


def normalize_mould_number(value: object) -> str:
    return str(value).strip() if value is not None else ""


def read_oracle_changeovers(connection) -> tuple[list[OracleChangeover], int]:
    changeovers: list[OracleChangeover] = []
    skipped = 0

    with connection.cursor() as cursor:
        cursor.execute(ORACLE_QUERY)
        for row in cursor:
            order_number = normalize_mould_number(row[0])
            from_number = normalize_mould_number(row[5])
            to_number = normalize_mould_number(row[6])
            needed_date = row[7]

            if not from_number or not to_number or needed_date is None:
                skipped += 1
                LOGGER.warning(
                    "Pomijam niekompletne zamówienie %r (z=%r, na=%r, termin=%r)",
                    order_number,
                    from_number,
                    to_number,
                    needed_date,
                )
                continue

            available_date = row[3] or row[2] or row[4] or needed_date
            if row[3] is None:
                LOGGER.warning(
                    "Zamówienie %r nie ma DATA_ZATWIERDZENIA; "
                    "available_date ustawiono na %s",
                    order_number,
                    available_date,
                )

            changeovers.append(
                OracleChangeover(
                    order_number=order_number,
                    available_date=available_date,
                    from_mould_number=from_number,
                    to_mould_number=to_number,
                    needed_date=needed_date,
                )
            )

    return changeovers, skipped


def load_mould_ids(cursor, changeovers: list[OracleChangeover]) -> dict[str, int]:
    mould_numbers = sorted(
        {
            number
            for changeover in changeovers
            for number in (
                changeover.from_mould_number,
                changeover.to_mould_number,
            )
        }
    )
    if not mould_numbers:
        return {}

    cursor.execute(
        "SELECT id, mould_number FROM moulds WHERE mould_number = ANY(%s)",
        (mould_numbers,),
    )
    return {normalize_mould_number(number): mould_id for mould_id, number in cursor}


def sync_changeovers(
    cursor,
    changeovers: list[OracleChangeover],
    skipped_invalid: int = 0,
) -> SyncResult:
    result = SyncResult(skipped_invalid=skipped_invalid)
    mould_ids = load_mould_ids(cursor, changeovers)

    # Chroni przed równoczesnym uruchomieniem dwóch kopii synchronizatora.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("synch_przezbrojenia",))

    for changeover in changeovers:
        from_mould_id = mould_ids.get(changeover.from_mould_number)
        to_mould_id = mould_ids.get(changeover.to_mould_number)

        if from_mould_id is None or to_mould_id is None:
            result.skipped_missing_mould += 1
            LOGGER.warning(
                "Pomijam zamówienie %r: brak formy w PostgreSQL (z=%r, na=%r)",
                changeover.order_number,
                changeover.from_mould_number,
                changeover.to_mould_number,
            )
            continue

        cursor.execute(
            """
            SELECT id, available_date
            FROM changeovers
            WHERE from_mould_id = %s
              AND to_mould_id = %s
              AND needed_date = %s
            ORDER BY id
            LIMIT 1
            """,
            (from_mould_id, to_mould_id, changeover.needed_date),
        )
        existing = cursor.fetchone()

        if existing is None:
            cursor.execute(
                """
                INSERT INTO changeovers (
                    from_mould_id,
                    to_mould_id,
                    available_date,
                    needed_date,
                    czy_wykonano,
                    updated_by
                )
                VALUES (%s, %s, %s, %s, FALSE, %s)
                """,
                (
                    from_mould_id,
                    to_mould_id,
                    changeover.available_date,
                    changeover.needed_date,
                    SYNC_USER,
                ),
            )
            result.inserted += 1
            continue

        changeover_id, current_available_date = existing
        if current_available_date == changeover.available_date:
            result.unchanged += 1
            continue

        cursor.execute(
            """
            UPDATE changeovers
            SET available_date = %s,
                updated_by = %s,
                updated = NOW()
            WHERE id = %s
            """,
            (changeover.available_date, SYNC_USER, changeover_id),
        )
        result.updated += 1

    return result


def refresh() -> SyncResult:
    with oracle_connection() as oracle:
        changeovers, skipped_invalid = read_oracle_changeovers(oracle)

    with postgres_connection() as postgres:
        with postgres.cursor() as cursor:
            result = sync_changeovers(cursor, changeovers, skipped_invalid)

    return result


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    result = refresh()
    LOGGER.info(
        "Synchronizacja zakończona: dodano=%d, zaktualizowano=%d, "
        "bez zmian=%d, pominięto niekompletne=%d, pominięto brakujące formy=%d",
        result.inserted,
        result.updated,
        result.unchanged,
        result.skipped_invalid,
        result.skipped_missing_mould,
    )


if __name__ == "__main__":
    main()

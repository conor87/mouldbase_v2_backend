"""Jednokierunkowa synchronizacja przezbrojeń z Oracle do PostgreSQL."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv

import oracledb
import psycopg2

load_dotenv("/etc/synch_przezbrojenia.env", override=False)

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
    is_completed: bool


@dataclass
class SyncResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_invalid: int = 0
    skipped_missing_mould: int = 0
    missing_changeovers: list["MissingChangeover"] = field(default_factory=list)


@dataclass(frozen=True)
class MissingChangeover:
    order_number: str
    from_mould_number: str
    to_mould_number: str
    available_date: datetime
    needed_date: datetime
    missing_from_mould: bool
    missing_to_mould: bool


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
                    is_completed=str(row[1] or "").strip().upper() == "T",
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


def prepare_missing_changeovers_registry(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS changeovers_sync_missing (
            id BIGSERIAL PRIMARY KEY,
            oracle_order_number TEXT NOT NULL,
            from_mould_number VARCHAR(128) NOT NULL,
            to_mould_number VARCHAR(128) NOT NULL,
            available_date TIMESTAMP NOT NULL,
            needed_date TIMESTAMP NOT NULL,
            missing_from_mould BOOLEAN NOT NULL,
            missing_to_mould BOOLEAN NOT NULL,
            first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
            last_seen TIMESTAMP NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMP NULL,
            UNIQUE (
                oracle_order_number,
                from_mould_number,
                to_mould_number,
                needed_date
            )
        )
        """
    )
    # Pozycje nadal obecne w Oracle zostaną poniżej ponownie oznaczone jako aktywne.
    cursor.execute(
        """
        UPDATE changeovers_sync_missing
        SET resolved_at = NOW()
        WHERE resolved_at IS NULL
        """
    )


def record_missing_changeover(
    cursor,
    changeover: OracleChangeover,
    missing_from_mould: bool,
    missing_to_mould: bool,
) -> None:
    cursor.execute(
        """
        INSERT INTO changeovers_sync_missing (
            oracle_order_number,
            from_mould_number,
            to_mould_number,
            available_date,
            needed_date,
            missing_from_mould,
            missing_to_mould,
            resolved_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NULL)
        ON CONFLICT (
            oracle_order_number,
            from_mould_number,
            to_mould_number,
            needed_date
        )
        DO UPDATE SET
            available_date = EXCLUDED.available_date,
            missing_from_mould = EXCLUDED.missing_from_mould,
            missing_to_mould = EXCLUDED.missing_to_mould,
            last_seen = NOW(),
            resolved_at = NULL
        """,
        (
            changeover.order_number,
            changeover.from_mould_number,
            changeover.to_mould_number,
            changeover.available_date,
            changeover.needed_date,
            missing_from_mould,
            missing_to_mould,
        ),
    )


def load_unresolved_missing_changeovers(cursor) -> list[MissingChangeover]:
    cursor.execute(
        """
        SELECT
            oracle_order_number,
            from_mould_number,
            to_mould_number,
            available_date,
            needed_date,
            missing_from_mould,
            missing_to_mould
        FROM changeovers_sync_missing
        WHERE resolved_at IS NULL
        ORDER BY needed_date, oracle_order_number
        """
    )
    return [MissingChangeover(*row) for row in cursor.fetchall()]


def prepare_sync_status_registry(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS changeovers_sync_status (
            sync_name TEXT PRIMARY KEY,
            last_success_at TIMESTAMPTZ NOT NULL,
            inserted INTEGER NOT NULL DEFAULT 0,
            updated INTEGER NOT NULL DEFAULT 0,
            unchanged INTEGER NOT NULL DEFAULT 0,
            skipped_invalid INTEGER NOT NULL DEFAULT 0,
            missing_moulds INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def record_sync_success(cursor, result: SyncResult) -> None:
    cursor.execute(
        """
        INSERT INTO changeovers_sync_status (
            sync_name,
            last_success_at,
            inserted,
            updated,
            unchanged,
            skipped_invalid,
            missing_moulds
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
        ON CONFLICT (sync_name)
        DO UPDATE SET
            last_success_at = EXCLUDED.last_success_at,
            inserted = EXCLUDED.inserted,
            updated = EXCLUDED.updated,
            unchanged = EXCLUDED.unchanged,
            skipped_invalid = EXCLUDED.skipped_invalid,
            missing_moulds = EXCLUDED.missing_moulds
        """,
        (
            "changeovers",
            result.inserted,
            result.updated,
            result.unchanged,
            result.skipped_invalid,
            result.skipped_missing_mould,
        ),
    )


def sync_changeovers(
    cursor,
    changeovers: list[OracleChangeover],
    skipped_invalid: int = 0,
) -> SyncResult:
    result = SyncResult(skipped_invalid=skipped_invalid)

    # Chroni przed równoczesnym uruchomieniem dwóch kopii synchronizatora.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("synch_przezbrojenia",))
    prepare_missing_changeovers_registry(cursor)
    prepare_sync_status_registry(cursor)
    mould_ids = load_mould_ids(cursor, changeovers)

    for changeover in changeovers:
        from_mould_id = mould_ids.get(changeover.from_mould_number)
        to_mould_id = mould_ids.get(changeover.to_mould_number)

        if from_mould_id is None or to_mould_id is None:
            result.skipped_missing_mould += 1
            record_missing_changeover(
                cursor,
                changeover,
                missing_from_mould=from_mould_id is None,
                missing_to_mould=to_mould_id is None,
            )
            LOGGER.warning(
                "Zapisuję w rejestrze braków zamówienie %r "
                "(z=%r%s, na=%r%s, termin=%s)",
                changeover.order_number,
                changeover.from_mould_number,
                " — BRAK" if from_mould_id is None else "",
                changeover.to_mould_number,
                " — BRAK" if to_mould_id is None else "",
                changeover.needed_date,
            )
            continue

        # Synchronizacja jest dopisująca: istniejących rekordów nie aktualizujemy.
        # Nowe wystąpienie tej samej pary form w innym terminie nadal jest osobnym wpisem.
        cursor.execute(
            """
            SELECT id
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

        if existing is not None:
            result.unchanged += 1
            continue

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
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                from_mould_id,
                to_mould_id,
                changeover.available_date,
                changeover.needed_date,
                changeover.is_completed,
                SYNC_USER,
            ),
        )
        result.inserted += 1

    result.missing_changeovers = load_unresolved_missing_changeovers(cursor)
    record_sync_success(cursor, result)
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
        "bez zmian=%d, pominięto niekompletne=%d, "
        "zarejestrowano brakujące formy=%d",
        result.inserted,
        result.updated,
        result.unchanged,
        result.skipped_invalid,
        result.skipped_missing_mould,
    )

    if not result.missing_changeovers:
        LOGGER.info("Raport brakujących form: brak nierozwiązanych pozycji.")
        return

    LOGGER.warning(
        "Raport brakujących form — nierozwiązane przezbrojenia: %d",
        len(result.missing_changeovers),
    )
    for missing in result.missing_changeovers:
        LOGGER.warning(
            "  zamówienie=%r | z=%s%s | na=%s%s | dostępna=%s | potrzebna=%s",
            missing.order_number,
            missing.from_mould_number,
            " [BRAK W MOULDS]" if missing.missing_from_mould else "",
            missing.to_mould_number,
            " [BRAK W MOULDS]" if missing.missing_to_mould else "",
            missing.available_date,
            missing.needed_date,
        )


if __name__ == "__main__":
    main()

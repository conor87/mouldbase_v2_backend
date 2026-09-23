"""Jednokierunkowa synchronizacja planu produkcji Oracle -> PostgreSQL."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from dotenv import load_dotenv

import oracledb
import psycopg2
from psycopg2.extras import execute_values

load_dotenv("/etc/synch_przezbrojenia.env", override=False)


LOGGER = logging.getLogger("synch_produkcja")

ORACLE_QUERY = r"""
SELECT
    q.forma,
    q.data,
    i.Nazwa_Czesci AS nazwa,
    q.wyrob,
    (select
min(mrp_harm_pcg.opcja_data_konca((select max(hoz.ID) from mrp_harm_opcje_zlecen hoz where hoz.NUMER_ZLECENIA=hop.NUMER_ZLECENIA)) -ratio_01_lamela_harm.DAJ_CZAS_ZLEC_H((select max(hoz.ID) from mrp_harm_opcje_zlecen hoz where hoz.NUMER_ZLECENIA=hop.NUMER_ZLECENIA))/24)
from mrp_wykorzystanie_prz_pom_mz pom
inner join mrp_harm_operacje hop on pom.ID_OPERACJI=hop.ID_mz where hop.id_harm in (971367,971374,971380,896750)  and pom.INDEKS_CZESCI=q.forma
and nvl((select nvl(status_l, 'Otwarte') from ratio_harm_statusy_zlecen sz where  hop.NUMER_ZLECENIA = sz.numer_zlecenia), 'Otwarte')='Otwarte' ) AS produkcja_od,
    (select
max(mrp_harm_pcg.opcja_data_konca((select max(hoz.ID) from mrp_harm_opcje_zlecen hoz where hoz.NUMER_ZLECENIA=hop.NUMER_ZLECENIA))) as data_do
from mrp_wykorzystanie_prz_pom_mz pom inner join mrp_harm_operacje hop on pom.ID_OPERACJI=hop.ID_mz
where  hop.id_harm in (971367,971374,971380,896750) and pom.INDEKS_CZESCI=q.forma
 and nvl((select nvl(status_l, 'Otwarte') from ratio_harm_statusy_zlecen sz where  hop.NUMER_ZLECENIA = sz.numer_zlecenia), 'Otwarte')='Otwarte'  ) AS produkcja_do,
    CASE
WHEN (INstr(UPPER(i.Nazwa_Czesci),'FINEZJA 190',1,1)>0) THEN 11
WHEN (INstr(UPPER(i.Nazwa_Czesci),'FINEZJA 250',1,1)>0) THEN 12
WHEN (INstr(UPPER(i.Nazwa_Czesci),'FINEZJA 300',1,1)>0) THEN 13
WHEN (INstr(UPPER(i.Nazwa_Czesci),'FINEZJA 350',1,1)>0) THEN 14
WHEN (INstr(UPPER(i.Nazwa_Czesci),'FINEZJA 400',1,1)>0) THEN 15
WHEN (INstr(UPPER(i.Nazwa_Czesci),'LILIA FI 190',1,1)>0) THEN 16
WHEN (INstr(UPPER(i.Nazwa_Czesci),'LILIA FI 250',1,1)>0) THEN 17  
WHEN (INstr(UPPER(i.Nazwa_Czesci),'LILIA FI 300',1,1)>0) THEN 18
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUKA 190',1,1)>0) THEN 21  
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUKA 250',1,1)>0) THEN 22
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUKA 300',1,1)>0) THEN 23
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUKA 400',1,1)>0) THEN 24
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA DUET 140',1,1)>0) THEN 25
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA AZTEK 140',1,1)>0) THEN 25
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA DUET 190',1,1)>0) THEN 26
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA AZTEK 190',1,1)>0) THEN 26
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA SOLO 190',1,1)>0) THEN 26
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA DUET 250',1,1)>0) THEN 27
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA AZTEK 250',1,1)>0) THEN 27
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA SOLO 250',1,1)>0) THEN 27
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA DUET 300',1,1)>0) THEN 28
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA AZTEK 300',1,1)>0) THEN 28
WHEN (INstr(UPPER(i.Nazwa_Czesci),'A DONICZKA SOLO 300',1,1)>0) THEN 28
WHEN (INstr(UPPER(i.Nazwa_Czesci),'SKRZYNKA AZTEK 400',1,1)>0) THEN 29
WHEN (INstr(UPPER(i.Nazwa_Czesci),'SKRZYNKA DUET 400',1,1)>0) THEN 29
WHEN (INstr(UPPER(i.Nazwa_Czesci),'SKRZYNKA AZTEK 600',1,1)>0) THEN 30
WHEN (INstr(UPPER(i.Nazwa_Czesci),'SKRZYNKA DUET 600',1,1)>0) THEN 30
WHEN (INstr(UPPER(i.Nazwa_Czesci),'ROMA 290/FRIDA 300 - WKŁADKA DNA',1,1)>0) THEN 31
WHEN (INstr(UPPER(i.Nazwa_Czesci),'ROMA 470 - WKŁADKA DNA',1,1)>0) THEN 31
WHEN (INstr(UPPER(i.Nazwa_Czesci),'WKŁAD DO DONICZKA',1,1)>0) THEN 32
WHEN (INstr(UPPER(i.Nazwa_Czesci),'ROMA 240/FRIDA 260 - WKŁADKA DNA',1,1)>0) THEN 33
WHEN (INstr(UPPER(i.Nazwa_Czesci),'ROMA 330/FRIDA 340 - WKŁADKA DNA',1,1)>0) THEN 33
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JERSEY FI 110',1,1)>0) THEN 34
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUMPER  FI 110',1,1)>0) THEN 34
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JERSEY FI 160',1,1)>0) THEN 35
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUMPER FI 160',1,1)>0) THEN 35
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JERSEY FI 190',1,1)>0) THEN 36
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUMPER FI 190',1,1)>0) THEN 36
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JERSEY FI 220',1,1)>0) THEN 37
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUMPER  FI 220',1,1)>0) THEN 37
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JERSEY FI 260',1,1)>0) THEN 38
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUMPER  FI 260',1,1)>0) THEN 38
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JERSEY FI 300',1,1)>0) THEN 39
WHEN (INstr(UPPER(i.Nazwa_Czesci),'JUMPER FI 300',1,1)>0) THEN 39
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MIRA FI 190 - WKŁADKA',1,1)>0) THEN 40
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MIRA FI 145 - WKŁADKA',1,1)>0) THEN 40
WHEN (INstr(UPPER(i.Nazwa_Czesci),'KWIETNIK BEGONIA',1,1)>0) THEN 41
WHEN (INstr(UPPER(i.Nazwa_Czesci),'KWIETNIK WERBENA',1,1)>0) THEN 42
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MIRA FI 300 - WKŁADKA',1,1)>0) THEN 43
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MIRA FI 390 - WKŁADKA',1,1)>0) THEN 43
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA ROMA 240',1,1)>0) THEN 44
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA ROMA 330',1,1)>0) THEN 45
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA ROMA 430 OWAL',1,1)>0) THEN 46
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA MIRA FI 240',1,1)>0) THEN 47
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA MIRA FI 300',1,1)>0) THEN 48
WHEN (INstr(UPPER(i.Nazwa_Czesci),'KWIETNIK KARO 400X400X400',1,1)>0) THEN 49
WHEN (INstr(UPPER(i.Nazwa_Czesci),'KWIETNIK KARO 400X400X600',1,1)>0) THEN 50
WHEN (INstr(UPPER(i.Nazwa_Czesci),'KWIETNIK KARO 800X400X400',1,1)>0) THEN 51
WHEN (INstr(UPPER(i.Nazwa_Czesci),'PODPÓRKA POD ROŚLINY',1,1)>0) THEN 52
WHEN (INstr(UPPER(i.Nazwa_Czesci),'NAWADNIAJĄCY',1,1)>0) THEN 55
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA JERSEY 300-',1,1)>0) THEN 56
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA JERSEY 240-',1,1)>0) THEN 56
WHEN (INstr(UPPER(i.Nazwa_Czesci),'MISA WISZĄCA JERSEY 240-',1,1)>0) THEN 56
ELSE 66 END AS typ
FROM (
SELECT
    s.TOOLS AS forma,
    TO_CHAR(MAX(r.czas), 'YYYY-MM-DD') AS data,
    Case REPLACE(REPLACE(SUBSTR(s.Nazwa, 1, INSTR(s.Nazwa, '-', 1, 1) - 1), 'FS', 'LA'), 'ED', 'LA')
when 'IK548' then 'LA548'
when 'LA765' then 'LA535'
when 'LA766' then 'LA536'
when 'LA767' then 'LA546'
when 'LA768' then 'LA761'
when 'LA769' then 'LA762'
when 'LA764' then 'LA763'
when 'LA772' then 'LA770'
when 'LA296' then 'LA794'
when 'LA293' then 'LA791'
when 'LA299' then 'LA535'
when 'LA300' then 'LA536'
when 'LA294' then 'LA792'
when 'LA295' then 'LA793'
when 'LA301' then 'LA546'
when 'LA835' then 'LA598'
when 'LA836' then 'LA599'
when 'LA230' then 'LA798'
--Magnoa Jupmer i Lilia Jumper recycled
when 'LA664' then 'LA750'
when 'LA671' then 'LA750'
when 'LA665' then 'LA751'
when 'LA666' then 'LA752'
when 'LA667' then 'LA753'
when 'LA674' then 'LA753'
when 'LA675' then 'LA754'
when 'LA668' then 'LA754'
when 'LA871' then 'LA754'
when 'LA669' then 'LA755'
when 'LA676' then 'LA755'
when 'LA872' then 'LA755'
when 'LA670' then 'LA756'
when 'LA677' then 'LA756'
when 'LA898' then 'LA863'
when 'LA899' then 'LA864'
when 'LA875' then 'LA864'
when 'LA900' then 'LA865'
when 'LA876' then 'LA865'
when 'LA919' then 'LA797'
when 'LA944' then 'LA797'
when 'LA884' then 'LA891'
when 'LA962' then 'LA950'
when 'LA956' then 'LA950'  
when 'LA942' then 'LA909'
when 'LA917' then 'LA909'
when 'LA933' then 'LA909'
when 'LA934' then 'LA910'
when 'LA943' then 'LA910'
when 'LA918' then 'LA910'
when 'LA976' then 'LA974'
when 'LA978' then 'LA974'
when 'LA980' then 'LA974'
when 'LA977' then 'LA975'
when 'LA979' then 'LA975'
when 'LA981' then 'LA975'
when 'LA968' then 'LA950'
when 'LA962' then 'LA950'
when 'LA956' then 'LA950'
when 'LA923' then 'LA798'
when 'LA946' then 'LA798'
when 'LA958' then 'LA952'
when 'LA964' then 'LA952'
when 'LA970' then 'LA952'
when 'LA924' then 'LA799'
when 'LA947' then 'LA799'
when 'LA959' then 'LA953'
when 'LA965' then 'LA953'
when 'LA971' then 'LA953'
when 'LA892' then 'LA885'
else REPLACE(REPLACE(SUBSTR(s.Nazwa, 1, INSTR(s.Nazwa, '-', 1, 1) - 1), 'FS', 'LA'), 'ED', 'LA')
end AS wyrob
from RATIO_GOLEM_RAPORTH r
left join RATIO_GOLEM_SERIE s on s.id=r.IDS
and r.ids is not null and r.ids>0
and (r.D_TPP)>300
and r.czas > DATE '2020-01-01'
--wyjątki z pomyloną formą
and s.Nazwa not in ('LA532-82_PP15.03/01094','LA572_PP15.05/00196','LA601-74_PP15.07/00121','LA548_PP16.08/00135','EM207-01_PP17.03/00019','LA750-74_PP19.06/00436','PP21.06/00314','LA547-05_PP21.03/00869','LA864-50_QJ21.10/038','LA881-3-04_PPK21.12/0318','LA864-74_PP20.03/00390','LA936-82_PP22.07/00190','LA936-05_PP22.07/00164','LA916-2-04_PP23.06/01074')
and s.NAZWA not like '%_QJ%' and s.NAZWA not like '%_PPK%'
GROUP BY
    s.TOOLS,
    Case REPLACE(REPLACE(SUBSTR(s.Nazwa, 1, INSTR(s.Nazwa, '-', 1, 1) - 1), 'FS', 'LA'), 'ED', 'LA')
when 'IK548' then 'LA548'
when 'LA765' then 'LA535'
when 'LA766' then 'LA536'
when 'LA767' then 'LA546'
when 'LA768' then 'LA761'
when 'LA769' then 'LA762'
when 'LA764' then 'LA763'
when 'LA772' then 'LA770'
when 'LA296' then 'LA794'
when 'LA293' then 'LA791'
when 'LA299' then 'LA535'
when 'LA300' then 'LA536'
when 'LA294' then 'LA792'
when 'LA295' then 'LA793'
when 'LA301' then 'LA546'
when 'LA835' then 'LA598'
when 'LA836' then 'LA599'
when 'LA230' then 'LA798'
--Magnoa Jupmer i Lilia Jumper recycled
when 'LA664' then 'LA750'
when 'LA671' then 'LA750'
when 'LA665' then 'LA751'
when 'LA666' then 'LA752'
when 'LA667' then 'LA753'
when 'LA674' then 'LA753'
when 'LA675' then 'LA754'
when 'LA668' then 'LA754'
when 'LA871' then 'LA754'
when 'LA669' then 'LA755'
when 'LA676' then 'LA755'
when 'LA872' then 'LA755'
when 'LA670' then 'LA756'
when 'LA677' then 'LA756'
when 'LA898' then 'LA863'
when 'LA899' then 'LA864'
when 'LA875' then 'LA864'
when 'LA900' then 'LA865'
when 'LA876' then 'LA865'
when 'LA919' then 'LA797'
when 'LA944' then 'LA797'
when 'LA884' then 'LA891'
when 'LA962' then 'LA950'
when 'LA956' then 'LA950'  
when 'LA942' then 'LA909'
when 'LA917' then 'LA909'
when 'LA933' then 'LA909'
when 'LA934' then 'LA910'
when 'LA943' then 'LA910'
when 'LA918' then 'LA910'
when 'LA976' then 'LA974'
when 'LA978' then 'LA974'
when 'LA980' then 'LA974'
when 'LA977' then 'LA975'
when 'LA979' then 'LA975'
when 'LA981' then 'LA975'
when 'LA968' then 'LA950'
when 'LA962' then 'LA950'
when 'LA956' then 'LA950'
when 'LA923' then 'LA798'
when 'LA946' then 'LA798'
when 'LA958' then 'LA952'
when 'LA964' then 'LA952'
when 'LA970' then 'LA952'
when 'LA924' then 'LA799'
when 'LA947' then 'LA799'
when 'LA959' then 'LA953'
when 'LA965' then 'LA953'
when 'LA971' then 'LA953'
when 'LA892' then 'LA885'
else REPLACE(REPLACE(SUBSTR(s.Nazwa, 1, INSTR(s.Nazwa, '-', 1, 1) - 1), 'FS', 'LA'), 'ED', 'LA')
end
) q
LEFT JOIN indeksy i ON i.indeks_czesci = q.forma
"""


@dataclass(frozen=True)
class OracleProduction:
    forma: str
    data: str | None
    nazwa: str | None
    wyrob: str | None
    produkcja_od: str | None
    produkcja_do: str | None
    typ: int | None


@dataclass(frozen=True)
class SyncResult:
    fetched: int
    inserted: int
    skipped_invalid: int


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


def normalized_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def read_oracle_production(connection) -> tuple[list[OracleProduction], int]:
    production: list[OracleProduction] = []
    skipped = 0

    with connection.cursor() as cursor:
        cursor.execute(ORACLE_QUERY)
        for row in cursor:
            forma = normalized_text(row[0])
            if not forma:
                skipped += 1
                LOGGER.warning("Pomijam wiersz produkcji bez numeru formy: %r", row)
                continue

            production.append(
                OracleProduction(
                    forma=forma,
                    data=normalized_text(row[1]),
                    nazwa=normalized_text(row[2]),
                    wyrob=normalized_text(row[3]),
                    produkcja_od=normalized_text(row[4]),
                    produkcja_do=normalized_text(row[5]),
                    typ=int(row[6]) if row[6] is not None else None,
                )
            )

    return production, skipped


def prepare_production_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS public.produkcja (
            forma TEXT,
            data TEXT,
            nazwa TEXT,
            wyrob TEXT,
            produkcja_od TEXT,
            produkcja_do TEXT,
            typ INTEGER
        )
        """
    )


def prepare_sync_status_registry(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS public.production_sync_status (
            sync_name TEXT PRIMARY KEY,
            last_success_at TIMESTAMP NOT NULL,
            fetched INTEGER NOT NULL DEFAULT 0,
            inserted INTEGER NOT NULL DEFAULT 0,
            skipped_invalid INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def record_sync_success(cursor, result: SyncResult) -> None:
    cursor.execute(
        """
        INSERT INTO public.production_sync_status (
            sync_name,
            last_success_at,
            fetched,
            inserted,
            skipped_invalid
        )
        VALUES ('production', NOW(), %s, %s, %s)
        ON CONFLICT (sync_name) DO UPDATE
        SET last_success_at = EXCLUDED.last_success_at,
            fetched = EXCLUDED.fetched,
            inserted = EXCLUDED.inserted,
            skipped_invalid = EXCLUDED.skipped_invalid
        """,
        (result.fetched, result.inserted, result.skipped_invalid),
    )


def sync_production(
    cursor,
    production: list[OracleProduction],
    skipped_invalid: int = 0,
) -> SyncResult:
    if not production:
        raise RuntimeError(
            "Oracle nie zwrócił żadnych poprawnych wierszy produkcji; "
            "pozostawiam dotychczasową tabelę bez zmian."
        )

    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("synch_produkcja",))
    prepare_production_table(cursor)
    prepare_sync_status_registry(cursor)
    cursor.execute("TRUNCATE TABLE public.produkcja")

    execute_values(
        cursor,
        """
        INSERT INTO public.produkcja (
            forma,
            data,
            nazwa,
            wyrob,
            produkcja_od,
            produkcja_do,
            typ
        )
        VALUES %s
        """,
        [
            (
                row.forma,
                row.data,
                row.nazwa,
                row.wyrob,
                row.produkcja_od,
                row.produkcja_do,
                row.typ,
            )
            for row in production
        ],
        page_size=1000,
    )

    result = SyncResult(
        fetched=len(production) + skipped_invalid,
        inserted=len(production),
        skipped_invalid=skipped_invalid,
    )
    record_sync_success(cursor, result)
    return result


def refresh() -> SyncResult:
    with oracle_connection() as oracle:
        production, skipped_invalid = read_oracle_production(oracle)

    with postgres_connection() as postgres:
        with postgres.cursor() as cursor:
            result = sync_production(cursor, production, skipped_invalid)

    return result


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    result = refresh()
    LOGGER.info(
        "Synchronizacja produkcji zakończona: pobrano=%d, zapisano=%d, "
        "pominięto niepoprawne=%d",
        result.fetched,
        result.inserted,
        result.skipped_invalid,
    )


if __name__ == "__main__":
    main()

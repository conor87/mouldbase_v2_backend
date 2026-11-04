from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import get_db
from routers.auth import superadmin_required


router = APIRouter(
    prefix="/work-hours",
    tags=["work-hours"],
    dependencies=[Depends(superadmin_required)],
)
SOURCE_COLUMNS = {
    "work_hours": {"YEAR", "MONTH", "DAY", "task", "hours", "machine"},
    "work_hours_human": {"YEAR", "MONTH", "DAY", "task", "hours", "stk", "worker"},
    "stk": {"name", "item"},
    "stawki": {"okres", "st1", "st2", "st3", "st4", "st5", "st6", "st7"},
}

ENTRIES_SQL = """
    WITH machine_stk AS (
        SELECT item::text AS item, min(name::text) AS stk FROM stk GROUP BY item::text
    ), rates_raw AS (
        SELECT s.okres, v.stk,
               replace(substring(v.raw_rate::text from '[-+]?[0-9]+(?:[.,][0-9]+)?'), ',', '.')::numeric AS hourly_cost
        FROM stawki s
        CROSS JOIN LATERAL (VALUES
            ('1', s.st1), ('2', s.st2), ('3', s.st3), ('4', s.st4),
            ('5', s.st5), ('6', s.st6), ('7', s.st7)
        ) AS v(stk, raw_rate)
    ), rates AS (
        SELECT okres, stk, max(hourly_cost) AS hourly_cost
        FROM rates_raw
        WHERE okres ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' AND hourly_cost IS NOT NULL
        GROUP BY okres, stk
    ), average_rates AS (
        SELECT stk, avg(hourly_cost) AS hourly_cost
        FROM rates GROUP BY stk
    ), raw_entries AS (
        SELECT w."YEAR" AS year, w."MONTH" AS month, w."DAY" AS day,
               w.task, w.machine AS item, w.hours::numeric AS hours,
               'machine' AS source, s.stk
        FROM work_hours w JOIN machine_stk s ON s.item = w.machine::text
        WHERE s.stk IN ('1', '2', '3', '4', '5')
        UNION ALL
        SELECT "YEAR", "MONTH", "DAY", task, worker, hours::numeric,
               'human', stk::text FROM work_hours_human
        WHERE stk::text IN ('6', '7')
    ), dated AS (
        SELECT *, CASE
            WHEN year BETWEEN 1 AND 9999 AND month BETWEEN 1 AND 12 AND day BETWEEN 1 AND 31
            THEN make_date(year, month, 1) + (day - 1)
            ELSE NULL
        END AS work_date FROM raw_entries
    ), entries AS (
        SELECT dated.*, COALESCE(rates.hourly_cost, average_rates.hourly_cost) AS hourly_cost,
               dated.hours * COALESCE(rates.hourly_cost, average_rates.hourly_cost) AS cost,
               rates.hourly_cost IS NULL AND average_rates.hourly_cost IS NOT NULL AS used_average_rate
        FROM dated
        LEFT JOIN rates ON rates.stk = dated.stk
                       AND rates.okres = to_char(dated.work_date, 'YYYY-MM')
        LEFT JOIN average_rates ON average_rates.stk = dated.stk
        WHERE EXTRACT(YEAR FROM work_date) = year
          AND EXTRACT(MONTH FROM work_date) = month
          AND (:task IS NULL OR task = :task)
          AND (:date_from IS NULL OR work_date >= :date_from)
          AND (:date_to IS NULL OR work_date <= :date_to)
    )
"""


def check_sources(db: Session):
    missing = []
    for table, required_columns in SOURCE_COLUMNS.items():
        columns = set(db.execute(text("""
            SELECT a.attname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE n.nspname = current_schema() AND c.relname = :table
              AND a.attnum > 0 AND NOT a.attisdropped
        """), {"table": table}).scalars())
        if not required_columns <= columns:
            missing.append(table)
    if missing:
        raise HTTPException(503, f"Brak wymaganych kolumn w tabelach: {', '.join(missing)}")


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    check_sources(db)
    return [row[0] for row in db.execute(text("""
        SELECT DISTINCT task FROM (
            SELECT w.task FROM work_hours w
            JOIN stk s ON s.item::text = w.machine::text
            WHERE s.name::text IN ('1', '2', '3', '4', '5')
            UNION ALL
            SELECT task FROM work_hours_human WHERE stk::text IN ('6', '7')
        ) AS entries
        WHERE task IS NOT NULL AND btrim(task) <> ''
        ORDER BY task
    """)).all()]


@router.get("/summary")
def work_hours_summary(
    task: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Data od musi być nie późniejsza niż data do")
    check_sources(db)
    params = {"task": task or None, "date_from": date_from, "date_to": date_to}
    rows = db.execute(text(ENTRIES_SQL + """
        SELECT to_char(date_trunc('month', work_date), 'YYYY-MM') AS month,
               COALESCE(SUM(hours), 0) AS hours,
               COALESCE(SUM(hours) FILTER (WHERE source = 'machine'), 0) AS machine_hours,
               COALESCE(SUM(hours) FILTER (WHERE source = 'human'), 0) AS human_hours,
               COALESCE(SUM(cost), 0) AS cost,
               COALESCE(SUM(hours) FILTER (WHERE hourly_cost IS NULL), 0) AS unpriced_hours,
               COALESCE(SUM(hours) FILTER (WHERE used_average_rate), 0) AS average_rate_hours
        FROM entries
        GROUP BY date_trunc('month', work_date)
        ORDER BY date_trunc('month', work_date)
    """), params).mappings().all()
    months = [
        {"month": row["month"], "hours": float(row["hours"]),
         "machine_hours": float(row["machine_hours"]), "human_hours": float(row["human_hours"]),
         "cost": float(row["cost"]), "unpriced_hours": float(row["unpriced_hours"]),
         "average_rate_hours": float(row["average_rate_hours"])}
        for row in rows
    ]
    detail_rows = db.execute(text(ENTRIES_SQL + """
        SELECT COALESCE(stk, 'Brak STK') AS stk, task, source, item,
               SUM(hours) AS hours, SUM(cost) AS cost
        FROM entries
        GROUP BY COALESCE(stk, 'Brak STK'), task, source, item
        ORDER BY stk, task, source, item
    """), params).mappings().all()
    groups = {}
    for row in detail_rows:
        group = groups.setdefault(row["stk"], {"stk": row["stk"], "hours": 0, "cost": 0, "items": []})
        hours = float(row["hours"])
        cost = float(row["cost"]) if row["cost"] is not None else None
        group["hours"] += hours
        group["cost"] += cost or 0
        group["items"].append({"task": row["task"], "source": row["source"],
                               "item": row["item"], "hours": hours, "cost": cost})
    invalid_rows = db.execute(text("""
        WITH raw_entries AS (
            SELECT w."YEAR" AS year, w."MONTH" AS month, w."DAY" AS day, w.task
            FROM work_hours w JOIN stk s ON s.item::text = w.machine::text
            WHERE s.name::text IN ('1', '2', '3', '4', '5')
            UNION ALL
            SELECT "YEAR", "MONTH", "DAY", task FROM work_hours_human
            WHERE stk::text IN ('6', '7')
        ), dated AS (
            SELECT *, CASE
                WHEN year BETWEEN 1 AND 9999 AND month BETWEEN 1 AND 12 AND day BETWEEN 1 AND 31
                THEN make_date(year, month, 1) + (day - 1)
                ELSE NULL
            END AS work_date FROM raw_entries
        )
        SELECT count(*) FROM dated
        WHERE (:task IS NULL OR task = :task)
          AND (work_date IS NULL OR EXTRACT(YEAR FROM work_date) <> year
               OR EXTRACT(MONTH FROM work_date) <> month)
    """), {"task": task or None}).scalar()
    return {"months": months, "total_hours": sum(row["hours"] for row in months),
            "machine_hours": sum(row["machine_hours"] for row in months),
            "human_hours": sum(row["human_hours"] for row in months),
            "total_cost": sum(row["cost"] for row in months),
            "unpriced_hours": sum(row["unpriced_hours"] for row in months),
            "average_rate_hours": sum(row["average_rate_hours"] for row in months),
            "groups": list(groups.values()), "invalid_date_rows": invalid_rows}

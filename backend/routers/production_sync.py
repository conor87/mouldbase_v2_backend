from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import SessionLocal
from routers.auth import admin_required


LOGGER = logging.getLogger("production_sync")
SYNC_ERROR_LOG_PATH = Path(__file__).resolve().parents[1] / "synch_produkcja_errors.log"
router = APIRouter(prefix="/production", tags=["production-sync"])


def write_sync_error_log(exc: Exception) -> None:
    try:
        with SYNC_ERROR_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n{datetime.now().astimezone().isoformat()} "
                "Nie udało się zsynchronizować produkcji\n"
            )
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=log_file)
    except OSError:
        LOGGER.exception("Nie udało się zapisać pliku logu synchronizacji produkcji")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def read_sync_status(db: Session) -> dict:
    table_exists = db.execute(
        text("SELECT to_regclass('public.production_sync_status')")
    ).scalar()
    if table_exists is None:
        return {
            "last_success_at": None,
            "fetched": 0,
            "inserted": 0,
            "skipped_invalid": 0,
            "duplicates_removed": 0,
        }

    row = db.execute(
        text(
            """
            SELECT
                last_success_at,
                fetched,
                inserted,
                skipped_invalid,
                COALESCE(
                    (to_jsonb(status_row) ->> 'duplicates_removed')::integer,
                    0
                ) AS duplicates_removed
            FROM public.production_sync_status AS status_row
            WHERE sync_name = 'production'
            """
        )
    ).mappings().first()
    if row is None:
        return {
            "last_success_at": None,
            "fetched": 0,
            "inserted": 0,
            "skipped_invalid": 0,
            "duplicates_removed": 0,
        }
    return dict(row)


@router.get("/sync/status")
async def get_sync_status(db: Session = Depends(get_db)):
    return read_sync_status(db)


@router.post("/sync", dependencies=[Depends(admin_required)])
async def run_sync(db: Session = Depends(get_db)):
    try:
        from synch_produkcja import refresh

        result = await run_in_threadpool(refresh)
    except Exception as exc:
        LOGGER.exception("Nie udało się zsynchronizować produkcji")
        write_sync_error_log(exc)
        raise HTTPException(
            status_code=502,
            detail="Synchronizacja produkcji nie powiodła się. Sprawdź log backendu.",
        ) from exc

    status = read_sync_status(db)
    return {
        **status,
        "fetched": result.fetched,
        "inserted": result.inserted,
        "skipped_invalid": result.skipped_invalid,
        "duplicates_removed": result.duplicates_removed,
    }

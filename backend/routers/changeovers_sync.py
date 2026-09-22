from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import SessionLocal
from routers.auth import admin_required


LOGGER = logging.getLogger("changeovers_sync")
router = APIRouter(prefix="/changeovers", tags=["changeovers-sync"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def read_sync_status(db: Session) -> dict:
    table_exists = db.execute(
        text("SELECT to_regclass('public.changeovers_sync_status')")
    ).scalar()
    if table_exists is None:
        return {
            "last_success_at": None,
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped_invalid": 0,
            "missing_moulds": 0,
        }

    row = db.execute(
        text(
            """
            SELECT
                last_success_at,
                inserted,
                updated,
                unchanged,
                skipped_invalid,
                missing_moulds
            FROM changeovers_sync_status
            WHERE sync_name = 'changeovers'
            """
        )
    ).mappings().first()
    if row is None:
        return {
            "last_success_at": None,
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped_invalid": 0,
            "missing_moulds": 0,
        }
    return dict(row)


@router.get("/sync/status")
async def get_sync_status(db: Session = Depends(get_db)):
    return read_sync_status(db)


@router.post("/sync", dependencies=[Depends(admin_required)])
async def run_sync(db: Session = Depends(get_db)):
    try:
        from synch_przezbrojenia import refresh

        result = await run_in_threadpool(refresh)
    except Exception as exc:
        LOGGER.exception("Nie udało się zsynchronizować przezbrojeń")
        raise HTTPException(
            status_code=502,
            detail="Synchronizacja przezbrojeń nie powiodła się. Sprawdź log backendu.",
        ) from exc

    status = read_sync_status(db)
    return {
        **status,
        "inserted": result.inserted,
        "updated": result.updated,
        "unchanged": result.unchanged,
        "skipped_invalid": result.skipped_invalid,
        "missing_moulds": result.skipped_missing_mould,
    }

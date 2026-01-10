# routers/calendar_log.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import SessionLocal
from models.calendar import CalendarEntry
from models.calendar_log import CalendarLog
from schemas.calendar_log import CalendarLogRead
from routers.auth import user_dependency, admin_required

router = APIRouter(prefix="/calendar", tags=["calendar-log"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/{entry_id}/log",
    response_model=List[CalendarLogRead],
    dependencies=[Depends(admin_required)],
)
async def get_calendar_log(
    entry_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    if not user or user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")

    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")

    rows = (
        db.query(CalendarLog)
        .filter(CalendarLog.calendar_entry_id == entry_id)
        .order_by(CalendarLog.id.desc())
        .limit(limit)
        .all()
    )
    return rows

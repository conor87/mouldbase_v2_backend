# routers/calendar.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import SessionLocal, db_dependency
from models.calendar import CalendarEntry
from models.calendar_log import CalendarLog
from models.mould import Mould
from schemas.calendar import CalendarRead

# auth
from routers.auth import user_dependency, admin_required

router = APIRouter(prefix="/calendar", tags=["calendar"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_dt_or_none(val: Optional[str], field_name: str) -> Optional[datetime]:
    """
    Obsluga datetime-local z React: 'YYYY-MM-DDTHH:MM'
    plus tolerancja dla: 'YYYY-MM-DD HH:MM', pelny ISO z sekundami.
    Puste stringi -> None.
    """
    if val is None:
        return None
    s = val.strip()
    if s == "":
        return None

    try:
        s2 = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s2)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    raise HTTPException(status_code=400, detail=f"Invalid datetime format for '{field_name}' (use YYYY-MM-DDTHH:MM)")


def require_mould(db: Session, mould_id: int):
    m = db.query(Mould).filter(Mould.id == mould_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mould not found")
    return m


def get_username_from_user(user: Optional[dict]) -> Optional[str]:
    if not user:
        return None
    return user.get("username") or user.get("sub") or user.get("name")


def dump_calendar_entry(entry: CalendarEntry) -> dict:
    return {
        "id": entry.id,
        "mould_id": entry.mould_id,
        "start_date": entry.start_date.isoformat() if entry.start_date else None,
        "end_date": entry.end_date.isoformat() if entry.end_date else None,
        "comment": entry.comment,
        "is_active": bool(entry.is_active),
        "created_by": entry.created_by,
        "created": entry.created.isoformat() if entry.created else None,
        "updated": entry.updated.isoformat() if entry.updated else None,
    }


def add_log(
    db: Session,
    *,
    calendar_entry_id: int,
    action: str,
    old_data: Optional[dict],
    new_data: Optional[dict],
    updated_by: Optional[str],
):
    log = CalendarLog(
        calendar_entry_id=calendar_entry_id,
        action=action,
        old_data=old_data,
        new_data=new_data,
        updated_by=updated_by,
    )
    db.add(log)


@router.post("/", response_model=CalendarRead, dependencies=[Depends(admin_required)])
async def create_calendar_entry(
    mould_id: int = Form(...),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    require_mould(db, mould_id)

    username = get_username_from_user(user)
    entry = CalendarEntry(
        mould_id=mould_id,
        start_date=parse_dt_or_none(start_date, "start_date"),
        end_date=parse_dt_or_none(end_date, "end_date"),
        comment=comment,
        is_active=bool(is_active),
        created_by=username,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    add_log(
        db,
        calendar_entry_id=entry.id,
        action="CREATE",
        old_data=None,
        new_data=dump_calendar_entry(entry),
        updated_by=username,
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/", response_model=List[CalendarRead])
async def list_calendar_entries(
    db: db_dependency,
    search: str | None = Query(None, description="Szukana forma (mould_number)"),
    skip: int = 0,
    limit: int = 1000,
):
    query = db.query(CalendarEntry)

    if search:
        like = f"%{search}%"
        query = query.filter(CalendarEntry.mould.has(Mould.mould_number.ilike(like)))

    query = query.order_by(
        CalendarEntry.is_active.desc(),
        CalendarEntry.start_date.desc(),
        CalendarEntry.created.desc(),
    )

    return query.offset(skip).limit(limit).all()


@router.get("/{entry_id}", response_model=CalendarRead)
async def get_calendar_entry(
    entry_id: int,
    db: db_dependency,
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


@router.put("/{entry_id}", response_model=CalendarRead, dependencies=[Depends(admin_required)])
async def update_calendar_entry(
    entry_id: int,
    mould_id: Optional[int] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")

    old_snapshot = dump_calendar_entry(entry)
    if mould_id is not None:
        require_mould(db, mould_id)
        entry.mould_id = mould_id

    if start_date is not None:
        entry.start_date = parse_dt_or_none(start_date, "start_date")

    if end_date is not None:
        entry.end_date = parse_dt_or_none(end_date, "end_date")

    if comment is not None:
        entry.comment = comment

    if is_active is not None:
        entry.is_active = bool(is_active)

    db.add(entry)
    db.commit()
    db.refresh(entry)

    new_snapshot = dump_calendar_entry(entry)
    action = (
        "TOGGLE_STATUS"
        if (is_active is not None and old_snapshot.get("is_active") != new_snapshot.get("is_active"))
        else "UPDATE"
    )
    add_log(
        db,
        calendar_entry_id=entry.id,
        action=action,
        old_data=old_snapshot,
        new_data=new_snapshot,
        updated_by=get_username_from_user(user),
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_calendar_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")

    add_log(
        db,
        calendar_entry_id=entry.id,
        action="DELETE",
        old_data=dump_calendar_entry(entry),
        new_data=None,
        updated_by=get_username_from_user(user),
    )
    db.commit()

    db.delete(entry)
    db.commit()
    return

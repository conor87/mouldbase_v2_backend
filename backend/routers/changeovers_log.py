# routers/changeovers_log.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import SessionLocal
from models.changeovers import Changeover
from models.changeovers_log import ChangeoverLog
from schemas.changeovers_log import ChangeoverLogRead

from routers.auth import user_dependency, admin_required

router = APIRouter(prefix="/changeovers", tags=["changeovers-log"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/{changeover_id}/log",
    response_model=List[ChangeoverLogRead],
    dependencies=[Depends(admin_required)],  # min. admin -> potem dopinamy superadmin check
)
async def get_changeover_log(
    changeover_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: user_dependency = None,
):
    # tylko superadmin
    if not user or user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")

    # czy changeover istnieje
    co = db.query(Changeover).filter(Changeover.id == changeover_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Changeover not found")

    rows = (
        db.query(ChangeoverLog)
        .filter(ChangeoverLog.changeover_id == changeover_id)
        .order_by(ChangeoverLog.id.desc())
        .limit(limit)
        .all()
    )
    return rows

from typing import List

from fastapi import APIRouter

from db.database import db_dependency
from models.mes_session import MesSessionLog
from schemas.mes_session import MesSessionLogCreate, MesSessionLogRead

router = APIRouter(prefix="/mes-session", tags=["MES Session"])


@router.post("/logs", response_model=MesSessionLogRead, status_code=201)
def create_session_log(payload: MesSessionLogCreate, db: db_dependency):
    log = MesSessionLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/logs", response_model=List[MesSessionLogRead])
def list_session_logs(db: db_dependency):
    return db.query(MesSessionLog).order_by(MesSessionLog.id.desc()).all()

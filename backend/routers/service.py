from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import db_dependency
from models.service import ServiceWorkstation, ServiceLog
from models.user import Users
from routers.auth import user_required, admin_required, superadmin_required, user_dependency
from schemas.service import (
    ServiceWorkstationCreate,
    ServiceWorkstationUpdate,
    ServiceWorkstationRead,
    ServiceLogCreate,
    ServiceLogUpdate,
    ServiceLogRead,
)

router = APIRouter(prefix="/service", tags=["service"])


def require_row(db: Session, model, row_id: int, label: str):
    obj = db.query(model).filter(model.id == row_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} with id {row_id} not found")
    return obj


def commit_or_409(db: Session, detail: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail)


# ─── Service Workstations ───────────────────────────────────────────────────

@router.get("/workstations", response_model=List[ServiceWorkstationRead], dependencies=[Depends(user_required)])
async def list_service_workstations(db: db_dependency):
    rows = (
        db.query(ServiceWorkstation, Users.username)
        .outerjoin(Users, Users.id == ServiceWorkstation.user_id)
        .order_by(ServiceWorkstation.nazwa_stanowiska.asc())
        .all()
    )
    return [
        ServiceWorkstationRead.model_validate(workstation).model_copy(
            update={"operator_username": username}
        )
        for workstation, username in rows
    ]


@router.post("/workstations", response_model=ServiceWorkstationRead, dependencies=[Depends(admin_required)])
async def create_service_workstation(payload: ServiceWorkstationCreate, db: db_dependency):
    data = payload.model_dump()
    if data.get("user_id") is not None:
        require_row(db, Users, data["user_id"], "User")
    obj = ServiceWorkstation(**data)
    db.add(obj)
    commit_or_409(db, "Service workstation already exists")
    db.refresh(obj)
    return obj


@router.put("/workstations/{workstation_id}", response_model=ServiceWorkstationRead, dependencies=[Depends(user_required)])
async def update_service_workstation(
    workstation_id: int,
    payload: ServiceWorkstationUpdate,
    db: db_dependency,
    user: user_dependency,
):
    obj = (
        db.query(ServiceWorkstation)
        .filter(ServiceWorkstation.id == workstation_id)
        .with_for_update()
        .first()
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono stanowiska serwisowego")
    if obj.user_id is not None and obj.user_id != user["id"]:
        raise HTTPException(status_code=409, detail="Stanowisko jest zajęte przez innego użytkownika")
    data = payload.model_dump(exclude_unset=True)
    if "user_id" in data and data["user_id"] is not None:
        if data["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Stanowisko można przypisać tylko do siebie")
        require_row(db, Users, data["user_id"], "User")
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Service workstation already exists")
    db.refresh(obj)
    return obj


@router.delete("/workstations/{workstation_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_service_workstation(workstation_id: int, db: db_dependency):
    obj = require_row(db, ServiceWorkstation, workstation_id, "Service workstation")
    db.delete(obj)
    commit_or_409(db, "Service workstation could not be deleted")
    return


# ─── Service Logs ───────────────────────────────────────────────────────────

@router.get("/logs", response_model=List[ServiceLogRead])
async def list_service_logs(db: db_dependency):
    return db.query(ServiceLog).order_by(ServiceLog.id.desc()).all()


@router.post("/logs", response_model=ServiceLogRead, dependencies=[Depends(user_required)])
async def create_service_log(payload: ServiceLogCreate, db: db_dependency):
    data = payload.model_dump()
    if not data.get("created_at"):
        data["created_at"] = datetime.now().isoformat()
    obj = ServiceLog(**data)
    db.add(obj)
    commit_or_409(db, "Service log could not be created")
    db.refresh(obj)
    return obj


@router.put("/logs/{log_id}", response_model=ServiceLogRead, dependencies=[Depends(admin_required)])
async def update_service_log(log_id: int, payload: ServiceLogUpdate, db: db_dependency):
    obj = require_row(db, ServiceLog, log_id, "Service log")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Service log could not be updated")
    db.refresh(obj)
    return obj


@router.delete("/logs/{log_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_service_log(log_id: int, db: db_dependency):
    obj = require_row(db, ServiceLog, log_id, "Service log")
    db.delete(obj)
    commit_or_409(db, "Service log could not be deleted")
    return

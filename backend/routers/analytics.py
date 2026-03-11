from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from db.database import db_dependency
from models.analytics import AnalyticaMachines, AnalyticaWorkers
from models.production import MachineStatus, Operation, OperationLog, ProductionOrder, ProductionTask, Workstation
from models.user import Users
from routers.auth import admin_required, user_required
from schemas.analytics import (
    MachineCard, MachineCardResponse, MachineCardSave, MachineEntry,
    WorkerCard, WorkerCardResponse, WorkerCardSave, WorkerEntry,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# status_no values that represent active work — only these count towards work time
WORK_STATUS_NOS = {1, 2, 3}  # Praca z operatorem, Praca bez operatora, Ustawianie


def _get_work_status_ids(db: Session) -> set:
    """Get status IDs that represent active work (praca z operatorem, bez operatora, ustawianie)."""
    rows = db.query(MachineStatus.id).filter(MachineStatus.status_no.in_(WORK_STATUS_NOS)).all()
    return {r.id for r in rows}


def _compute_from_logs(db: Session, target_date: date) -> dict:
    """
    Compute worker time per workstation from operation_logs for a given date.
    Sequential processing: only count time when current status is a work status
    (Praca z operatorem, Praca bez operatora, Ustawianie).
    Returns {user_id: {workstation_id: minutes}}.
    """
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    work_ids = _get_work_status_ids(db)

    logs = (
        db.query(OperationLog)
        .filter(OperationLog.created_at >= day_start, OperationLog.created_at < day_end)
        .filter(OperationLog.user_id.isnot(None))
        .filter(OperationLog.workstation_id.isnot(None))
        .order_by(OperationLog.user_id, OperationLog.created_at)
        .all()
    )

    result = {}
    user_logs = {}
    for log in logs:
        user_logs.setdefault(log.user_id, []).append(log)

    for user_id, u_logs in user_logs.items():
        ws_minutes = {}
        for i in range(len(u_logs) - 1):
            current = u_logs[i]
            # Only count time when machine is in a work status
            if current.status_id not in work_ids:
                continue
            next_log = u_logs[i + 1]
            delta = (next_log.created_at - current.created_at).total_seconds() / 60.0
            if delta > 480:
                delta = 0
            ws_id = current.workstation_id
            ws_minutes[ws_id] = ws_minutes.get(ws_id, 0) + delta
        for ws_id, mins in ws_minutes.items():
            mins = round(mins)
            if mins > 0:
                result.setdefault(user_id, {})[ws_id] = mins

    return result


@router.get("/worker-cards", response_model=WorkerCardResponse, dependencies=[Depends(admin_required)])
async def get_worker_cards(target_date: date = Query(..., alias="date"), db: db_dependency = None):
    # Get all users
    users = db.query(Users.id, Users.username).all()
    user_map = {u.id: u.username for u in users}

    # Get workstation names
    workstations = db.query(Workstation.id, Workstation.name).all()
    ws_map = {ws.id: ws.name for ws in workstations}

    # Get saved analytics data for this date
    saved = db.query(AnalyticaWorkers).filter(AnalyticaWorkers.date == target_date).all()
    saved_by_user = {}
    for row in saved:
        saved_by_user.setdefault(row.user_id, []).append(row)

    # Compute from logs for users without saved data
    log_data = _compute_from_logs(db, target_date)

    workers = []
    # Collect all user_ids that have either saved data or log data
    all_user_ids = set(saved_by_user.keys()) | set(log_data.keys())

    for user_id in sorted(all_user_ids):
        username = user_map.get(user_id, f"User #{user_id}")

        if user_id in saved_by_user:
            entries = [
                WorkerEntry(
                    workstation_id=row.workstation_id,
                    workstation_name=ws_map.get(row.workstation_id, f"WS #{row.workstation_id}"),
                    minutes=row.minutes,
                )
                for row in saved_by_user[user_id]
            ]
            source = "saved"
        elif user_id in log_data:
            entries = [
                WorkerEntry(
                    workstation_id=ws_id,
                    workstation_name=ws_map.get(ws_id, f"WS #{ws_id}"),
                    minutes=mins,
                )
                for ws_id, mins in log_data[user_id].items()
            ]
            source = "logs"
        else:
            continue

        total = sum(e.minutes for e in entries)
        if total > 0:
            workers.append(WorkerCard(
                user_id=user_id,
                username=username,
                source=source,
                entries=entries,
                total_minutes=total,
            ))

    return WorkerCardResponse(date=target_date, workers=workers)


@router.post("/worker-cards", dependencies=[Depends(admin_required)])
async def save_worker_card(payload: WorkerCardSave, db: db_dependency = None):
    # Delete existing entries for this user+date
    db.query(AnalyticaWorkers).filter(
        AnalyticaWorkers.user_id == payload.user_id,
        AnalyticaWorkers.date == payload.date,
    ).delete()

    # Insert new entries
    for entry in payload.entries:
        if entry.minutes > 0:
            obj = AnalyticaWorkers(
                user_id=payload.user_id,
                date=payload.date,
                workstation_id=entry.workstation_id,
                minutes=entry.minutes,
            )
            db.add(obj)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not save worker card")

    return {"message": "Worker card saved", "user_id": payload.user_id, "date": str(payload.date)}


@router.delete("/worker-cards", dependencies=[Depends(admin_required)])
async def reset_worker_card(
    user_id: int = Query(...),
    target_date: date = Query(..., alias="date"),
    db: db_dependency = None,
):
    deleted = db.query(AnalyticaWorkers).filter(
        AnalyticaWorkers.user_id == user_id,
        AnalyticaWorkers.date == target_date,
    ).delete()

    db.commit()
    return {"message": f"Deleted {deleted} entries", "user_id": user_id, "date": str(target_date)}


# ==================== Machine cards ====================

def _compute_machine_from_logs(db: Session, target_date: date) -> dict:
    """
    Compute machine time per operation from operation_logs for a given date.
    Process logs PER MACHINE (workstation) — each machine is evaluated independently.
    A machine works when it has a work status (sno 1,2,3) and stops when it gets
    an end status. Intermediate logs on OTHER machines are irrelevant.
    Returns {workstation_id: {operation_id: minutes}}.
    """
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    work_ids = _get_work_status_ids(db)

    logs = (
        db.query(OperationLog)
        .filter(OperationLog.created_at >= day_start, OperationLog.created_at < day_end)
        .filter(OperationLog.workstation_id.isnot(None))
        .filter(OperationLog.operation_id.isnot(None))
        .order_by(OperationLog.workstation_id, OperationLog.created_at)
        .all()
    )

    result = {}
    # Group by workstation — machine-centric view
    ws_logs = {}
    for log in logs:
        ws_logs.setdefault(log.workstation_id, []).append(log)

    for ws_id, w_logs in ws_logs.items():
        op_minutes = {}
        for i in range(len(w_logs) - 1):
            current = w_logs[i]
            # Only count time when machine is in a work status
            if current.status_id not in work_ids:
                continue
            next_log = w_logs[i + 1]
            delta = (next_log.created_at - current.created_at).total_seconds() / 60.0
            if delta > 1440:  # 24h safety cap
                delta = 0
            op_id = current.operation_id
            op_minutes[op_id] = op_minutes.get(op_id, 0) + delta
        for op_id, mins in op_minutes.items():
            mins = round(mins)
            if mins > 0:
                result.setdefault(ws_id, {})[op_id] = mins

    return result


def _build_operation_label(op, task_map, order_map):
    task = task_map.get(op.task_id)
    order = order_map.get(task.order_id) if task else None
    parts = []
    if order:
        parts.append(order.order_number)
    if task:
        parts.append(task.detail_name or task.detail_number)
    parts.append(f"Op#{op.operation_no}")
    return " | ".join(parts)


@router.get("/machine-cards", response_model=MachineCardResponse, dependencies=[Depends(admin_required)])
async def get_machine_cards(target_date: date = Query(..., alias="date"), db: db_dependency = None):
    workstations = db.query(Workstation).all()
    ws_map = {ws.id: ws.name for ws in workstations}

    operations = db.query(Operation).all()
    op_map = {op.id: op for op in operations}

    tasks = db.query(ProductionTask).all()
    task_map = {t.id: t for t in tasks}

    orders = db.query(ProductionOrder).all()
    order_map = {o.id: o for o in orders}

    saved = db.query(AnalyticaMachines).filter(AnalyticaMachines.date == target_date).all()
    saved_by_ws = {}
    for row in saved:
        saved_by_ws.setdefault(row.workstation_id, []).append(row)

    log_data = _compute_machine_from_logs(db, target_date)

    machines = []
    all_ws_ids = set(saved_by_ws.keys()) | set(log_data.keys())

    for ws_id in sorted(all_ws_ids):
        ws_name = ws_map.get(ws_id, f"WS #{ws_id}")

        if ws_id in saved_by_ws:
            entries = []
            for row in saved_by_ws[ws_id]:
                op = op_map.get(row.operation_id)
                label = _build_operation_label(op, task_map, order_map) if op else f"Op #{row.operation_id}"
                order = None
                if op:
                    task = task_map.get(op.task_id)
                    order = order_map.get(task.order_id) if task else None
                entries.append(MachineEntry(
                    operation_id=row.operation_id,
                    operation_label=label,
                    order_number=order.order_number if order else None,
                    minutes=row.minutes,
                ))
            source = "saved"
        elif ws_id in log_data:
            entries = []
            for op_id, mins in log_data[ws_id].items():
                op = op_map.get(op_id)
                label = _build_operation_label(op, task_map, order_map) if op else f"Op #{op_id}"
                order = None
                if op:
                    task = task_map.get(op.task_id)
                    order = order_map.get(task.order_id) if task else None
                entries.append(MachineEntry(
                    operation_id=op_id,
                    operation_label=label,
                    order_number=order.order_number if order else None,
                    minutes=mins,
                ))
            source = "logs"
        else:
            continue

        total = sum(e.minutes for e in entries)
        if total > 0:
            machines.append(MachineCard(
                workstation_id=ws_id,
                workstation_name=ws_name,
                source=source,
                entries=entries,
                total_minutes=total,
            ))

    return MachineCardResponse(date=target_date, machines=machines)


@router.post("/machine-cards", dependencies=[Depends(admin_required)])
async def save_machine_card(payload: MachineCardSave, db: db_dependency = None):
    db.query(AnalyticaMachines).filter(
        AnalyticaMachines.workstation_id == payload.workstation_id,
        AnalyticaMachines.date == payload.date,
    ).delete()

    for entry in payload.entries:
        if entry.minutes > 0:
            obj = AnalyticaMachines(
                workstation_id=payload.workstation_id,
                date=payload.date,
                operation_id=entry.operation_id,
                minutes=entry.minutes,
            )
            db.add(obj)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not save machine card")

    return {"message": "Machine card saved", "workstation_id": payload.workstation_id, "date": str(payload.date)}


@router.delete("/machine-cards", dependencies=[Depends(admin_required)])
async def reset_machine_card(
    workstation_id: int = Query(...),
    target_date: date = Query(..., alias="date"),
    db: db_dependency = None,
):
    deleted = db.query(AnalyticaMachines).filter(
        AnalyticaMachines.workstation_id == workstation_id,
        AnalyticaMachines.date == target_date,
    ).delete()

    db.commit()
    return {"message": f"Deleted {deleted} entries", "workstation_id": workstation_id, "date": str(target_date)}

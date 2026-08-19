from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, or_
from sqlalchemy.orm import Session

from db.database import db_dependency
from models.analytics import AnalyticaMachines, AnalyticaService, AnalyticaWorkers
from models.production import MachineStatus, Operation, OperationLog, ProductionOrder, ProductionTask, Workstation
from models.changeovers import Changeover
from models.mould import Mould
from models.service import ServiceLog
from models.user import Users
from routers.auth import admin_required, user_required
from schemas.analytics import (
    MachineCard, MachineCardResponse, MachineCardSave, MachineEntry,
    ServiceCard, ServiceCardResponse, ServiceCardSave, ServiceEntry,
    WorkerCalendarDay, WorkerCalendarResponse, WorkerCalendarRow,
    WorkerCard, WorkerCardResponse, WorkerCardSave, WorkerEntry,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# status_no values that represent active work — only these count towards work time
WORK_STATUS_NOS = {1, 2, 3}  # Praca z operatorem, Praca bez operatora, Ustawianie
STOP_LOG_NOTES = {"Wylogowanie"}


def _get_work_status_ids(db: Session) -> set:
    """Get status IDs that represent active work (praca z operatorem, bez operatora, ustawianie)."""
    rows = db.query(MachineStatus.id).filter(MachineStatus.status_no.in_(WORK_STATUS_NOS)).all()
    return {r.id for r in rows}


def _is_work_interval_start(log: OperationLog, work_ids: set) -> bool:
    if (log.note or "").strip() in STOP_LOG_NOTES:
        return False
    return log.status_id in work_ids


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

    # Map operation_id -> order context
    op_ids = {log.operation_id for log in logs if log.operation_id}
    op_to_order = {}
    if op_ids:
        rows = (
            db.query(Operation.id, ProductionOrder.order_number, ProductionOrder.team, ProductionOrder.product_name)
            .join(ProductionTask, Operation.task_id == ProductionTask.id)
            .join(ProductionOrder, ProductionTask.order_id == ProductionOrder.id)
            .filter(Operation.id.in_(op_ids))
            .all()
        )
        op_to_order = {r.id: (r.order_number, r.team, r.product_name) for r in rows}

    result = {}
    # Group by (user_id, workstation_id, order_number) so concurrent machine work is tracked independently
    user_ws_logs = {}
    for log in logs:
        order_no, order_team, order_product_name = op_to_order.get(log.operation_id, (None, None, None)) if log.operation_id else (None, None, None)
        key = (log.user_id, log.workstation_id, order_no, order_team, order_product_name)
        user_ws_logs.setdefault(key, []).append(log)

    for (user_id, ws_id, order_no, order_team, order_product_name), ws_logs in user_ws_logs.items():
        total = 0
        for i in range(len(ws_logs) - 1):
            current = ws_logs[i]
            if not _is_work_interval_start(current, work_ids):
                continue
            next_log = ws_logs[i + 1]
            delta = (next_log.created_at - current.created_at).total_seconds() / 60.0
            if delta > 720:  # 12h safety cap; shifts can exceed 8h with overtime
                delta = 0
            total += delta
        mins = round(total)
        if mins > 0:
            result.setdefault(user_id, {})[(ws_id, order_no, order_team, order_product_name)] = mins

    return result


def _compute_worker_display_total(entries: dict) -> int:
    """
    Sum sequential orders on the same workstation, then take the longest
    workstation total as the worker's effective time for the day.
    """
    workstation_totals = {}
    for (ws_id, _order_no, _order_team, _order_product_name), minutes in entries.items():
        workstation_totals[ws_id] = workstation_totals.get(ws_id, 0) + minutes
    return max(workstation_totals.values(), default=0)


def _split_interval_by_shift(start: datetime, end: datetime) -> dict:
    current = start
    result = {}
    while current < end:
        day = current.date()
        if 6 <= current.hour < 14:
            label = "6-14"
            boundary = datetime.combine(day, datetime.min.time()) + timedelta(hours=14)
        elif 14 <= current.hour < 22:
            label = "14-22"
            boundary = datetime.combine(day, datetime.min.time()) + timedelta(hours=22)
        else:
            label = "22-6"
            boundary_day = day if current.hour < 6 else day + timedelta(days=1)
            boundary = datetime.combine(boundary_day, datetime.min.time()) + timedelta(hours=6)

        segment_end = min(end, boundary)
        minutes = (segment_end - current).total_seconds() / 60.0
        if minutes > 0:
            result[label] = result.get(label, 0) + minutes
        current = segment_end
    return result


def _compute_worker_shift_percentages(db: Session, target_date: date) -> dict:
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    work_ids = _get_work_status_ids(db)

    logs = (
        db.query(OperationLog)
        .filter(OperationLog.created_at >= day_start, OperationLog.created_at < day_end)
        .filter(OperationLog.user_id.isnot(None))
        .filter(OperationLog.workstation_id.isnot(None))
        .order_by(OperationLog.user_id, OperationLog.workstation_id, OperationLog.operation_id, OperationLog.created_at)
        .all()
    )

    grouped_logs = {}
    for log in logs:
        key = (log.user_id, log.workstation_id, log.operation_id)
        grouped_logs.setdefault(key, []).append(log)

    shift_minutes_by_ws = {}
    for (user_id, ws_id, _op_id), group in grouped_logs.items():
        for i in range(len(group) - 1):
            current = group[i]
            if not _is_work_interval_start(current, work_ids):
                continue
            next_log = group[i + 1]
            delta = (next_log.created_at - current.created_at).total_seconds() / 60.0
            if delta <= 0 or delta > 720:
                continue
            for label, minutes in _split_interval_by_shift(current.created_at, next_log.created_at).items():
                user_ws = shift_minutes_by_ws.setdefault(user_id, {}).setdefault(ws_id, {})
                user_ws[label] = user_ws.get(label, 0) + minutes

    shift_order = {"6-14": 0, "14-22": 1, "22-6": 2}
    result = {}
    for user_id, workstation_data in shift_minutes_by_ws.items():
        if not workstation_data:
            continue
        dominant_shifts = max(workstation_data.values(), key=lambda shifts: sum(shifts.values()))
        total = sum(dominant_shifts.values())
        if total <= 0:
            continue
        labels = sorted(dominant_shifts, key=lambda label: shift_order.get(label, 99))
        percentages = {label: round((dominant_shifts[label] / total) * 100) for label in labels}
        diff = 100 - sum(percentages.values())
        if diff and labels:
            labels_by_minutes = sorted(labels, key=lambda label: dominant_shifts[label], reverse=True)
            percentages[labels_by_minutes[0]] += diff
        result[user_id] = {"shifts": labels, "percentages": percentages}

    return result


@router.get("/worker-cards", response_model=WorkerCardResponse, dependencies=[Depends(admin_required)])
async def get_worker_cards(target_date: date = Query(..., alias="date"), db: db_dependency = None):
    # Get all users
    users = db.query(Users.id, Users.username).all()
    user_map = {u.id: u.username for u in users}

    # Get workstation names
    workstations = db.query(Workstation.id, Workstation.name).all()
    ws_map = {ws.id: ws.name for ws in workstations}

    orders = db.query(ProductionOrder.order_number, ProductionOrder.team, ProductionOrder.product_name).all()
    order_map = {o.order_number: o for o in orders}

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
                    order_number=row.order_number,
                    order_team=order_map[row.order_number].team if row.order_number in order_map else None,
                    order_product_name=order_map[row.order_number].product_name if row.order_number in order_map else None,
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
                    order_number=order_no,
                    order_team=order_team,
                    order_product_name=order_product_name,
                    minutes=mins,
                )
                for (ws_id, order_no, order_team, order_product_name), mins in log_data[user_id].items()
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


@router.get("/worker-calendar", response_model=WorkerCalendarResponse, dependencies=[Depends(admin_required)])
async def get_worker_calendar(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), db: db_dependency = None):
    try:
        month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month")

    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)

    month_days = [
        month_start + timedelta(days=offset)
        for offset in range((next_month - month_start).days)
    ]

    users = db.query(Users.id, Users.username).all()
    user_map = {u.id: u.username for u in users}
    worker_days = {}

    saved_rows = (
        db.query(AnalyticaWorkers)
        .filter(AnalyticaWorkers.date >= month_start, AnalyticaWorkers.date < next_month)
        .all()
    )
    saved_by_day_user = {}
    for row in saved_rows:
        saved_by_day_user.setdefault((row.date, row.user_id), {})[
            (row.workstation_id, row.order_number, None)
        ] = row.minutes

    for day in month_days:
        log_data = _compute_from_logs(db, day)
        shift_data = _compute_worker_shift_percentages(db, day)
        user_ids = {uid for (row_day, uid) in saved_by_day_user if row_day == day} | set(log_data.keys())
        for user_id in user_ids:
            entries = saved_by_day_user.get((day, user_id)) or log_data.get(user_id, {})
            minutes = _compute_worker_display_total(entries)
            if minutes > 0:
                worker_days.setdefault(user_id, {})[day] = {
                    "minutes": minutes,
                    "shifts": shift_data.get(user_id, {}).get("shifts", []),
                    "shift_percentages": shift_data.get(user_id, {}).get("percentages", {}),
                }

    workers = []
    for user_id in sorted(worker_days, key=lambda uid: user_map.get(uid, "")):
        days = [
            WorkerCalendarDay(
                date=day,
                minutes=data["minutes"],
                shifts=data["shifts"],
                shift_percentages=data["shift_percentages"],
            )
            for day, data in sorted(worker_days[user_id].items())
        ]
        workers.append(WorkerCalendarRow(
            user_id=user_id,
            username=user_map.get(user_id, f"User #{user_id}"),
            days=days,
            total_minutes=sum(day.minutes for day in days),
        ))

    return WorkerCalendarResponse(month=month, days=month_days, workers=workers)


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
                order_number=entry.order_number,
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
            if not _is_work_interval_start(current, work_ids):
                continue
            next_log = w_logs[i + 1]
            delta = (next_log.created_at - current.created_at).total_seconds() / 60.0
            if delta > 1440:  # 24h safety cap
                delta = 0
            op_id = current.operation_id
            user_id = current.user_id
            key = (op_id, user_id)
            op_minutes[key] = op_minutes.get(key, 0) + delta
        for (op_id, user_id), mins in op_minutes.items():
            mins = round(mins)
            if mins > 0:
                result.setdefault(ws_id, {})[(op_id, user_id)] = mins

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


def _sync_worker_cards_from_machine_cards(db: Session, target_date: date) -> None:
    rows = (
        db.query(AnalyticaMachines, ProductionOrder.order_number)
        .join(Operation, AnalyticaMachines.operation_id == Operation.id)
        .join(ProductionTask, Operation.task_id == ProductionTask.id)
        .join(ProductionOrder, ProductionTask.order_id == ProductionOrder.id)
        .filter(AnalyticaMachines.date == target_date)
        .filter(AnalyticaMachines.user_id.isnot(None))
        .filter(AnalyticaMachines.minutes > 0)
        .all()
    )

    totals = {}
    for machine_row, order_number in rows:
        key = (machine_row.user_id, machine_row.workstation_id, order_number)
        totals[key] = totals.get(key, 0) + machine_row.minutes

    db.query(AnalyticaWorkers).filter(AnalyticaWorkers.date == target_date).delete()
    for (user_id, workstation_id, order_number), minutes in totals.items():
        db.add(AnalyticaWorkers(
            user_id=user_id,
            date=target_date,
            workstation_id=workstation_id,
            order_number=order_number,
            minutes=minutes,
        ))


@router.get("/machine-cards", response_model=MachineCardResponse, dependencies=[Depends(admin_required)])
async def get_machine_cards(target_date: date = Query(..., alias="date"), db: db_dependency = None):
    users = db.query(Users.id, Users.username).all()
    user_map = {u.id: u.username for u in users}

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
                task = None
                if op:
                    task = task_map.get(op.task_id)
                    order = order_map.get(task.order_id) if task else None
                entries.append(MachineEntry(
                    operation_id=row.operation_id,
                    user_id=row.user_id,
                    username=user_map.get(row.user_id) if row.user_id else None,
                    operation_label=label,
                    order_number=order.order_number if order else None,
                    order_team=order.team if order else None,
                    order_product_name=order.product_name if order else None,
                    detail_name=(task.detail_name or task.detail_number) if task else None,
                    operation_no=op.operation_no if op else None,
                    operation_description=op.description if op else None,
                    minutes=row.minutes,
                ))
            source = "saved"
        elif ws_id in log_data:
            entries = []
            for (op_id, u_id), mins in log_data[ws_id].items():
                op = op_map.get(op_id)
                label = _build_operation_label(op, task_map, order_map) if op else f"Op #{op_id}"
                order = None
                task = None
                if op:
                    task = task_map.get(op.task_id)
                    order = order_map.get(task.order_id) if task else None
                entries.append(MachineEntry(
                    operation_id=op_id,
                    user_id=u_id,
                    username=user_map.get(u_id) if u_id else None,
                    operation_label=label,
                    order_number=order.order_number if order else None,
                    order_team=order.team if order else None,
                    order_product_name=order.product_name if order else None,
                    detail_name=(task.detail_name or task.detail_number) if task else None,
                    operation_no=op.operation_no if op else None,
                    operation_description=op.description if op else None,
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
                user_id=entry.user_id,
                minutes=entry.minutes,
            )
            db.add(obj)

    try:
        _sync_worker_cards_from_machine_cards(db, payload.date)
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

    try:
        _sync_worker_cards_from_machine_cards(db, target_date)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not reset machine card")
    return {"message": f"Deleted {deleted} entries", "workstation_id": workstation_id, "date": str(target_date)}


# ==================== Service cards ====================

SKIP_SERVICE_STATUSES = {"Koniec działań", "Wylogowanie", "Koniec przezbrojenia"}


def _parse_service_dt(s: str) -> Optional[datetime]:
    """Parse service log created_at string, handling Z suffix and milliseconds."""
    if not s:
        return None
    try:
        cleaned = s.replace("Z", "") if s.endswith("Z") else s
        dt = datetime.fromisoformat(cleaned)
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _compute_service_from_logs(db: Session, target_date: date) -> dict:
    """
    Compute service worker time per (activity_type, mould_number) from service_logs.
    Sequential processing: count time between consecutive logs per operator.
    Skip "Koniec działań" and "Wylogowanie" entries (no timer).
    Returns {operator_username: {(activity_type, mould_number): minutes}}.
    """
    day_start_str = target_date.isoformat()
    day_end_str = (target_date + timedelta(days=1)).isoformat()

    logs = (
        db.query(ServiceLog)
        .filter(ServiceLog.created_at >= day_start_str, ServiceLog.created_at < day_end_str)
        .filter(ServiceLog.operator.isnot(None))
        .filter(
            or_(ServiceLog.status_service.isnot(None), ServiceLog.status_changeover.isnot(None))
        )
        .order_by(ServiceLog.operator, ServiceLog.created_at)
        .all()
    )

    # Build mould_number lookup for changeover logs missing mould_number
    changeover_ids = {
        log.mes_activ_changeover_id
        for log in logs
        if log.mes_activ_changeover_id and not log.mould_number and log.status_changeover
    }
    changeover_mould_map = {}
    if changeover_ids:
        rows = (
            db.query(Changeover.id, Mould.mould_number)
            .join(Mould, Changeover.to_mould_id == Mould.id)
            .filter(Changeover.id.in_(changeover_ids))
            .all()
        )
        changeover_mould_map = {r.id: r.mould_number for r in rows}

    service_mould_map = {
        log.mes_activ_service_id: log.mould_number
        for log in logs
        if log.mes_activ_service_id and log.mould_number
    }

    op_logs = {}
    for log in logs:
        op_logs.setdefault(log.operator, []).append(log)

    result = {}
    for operator, o_logs in op_logs.items():
        activity_minutes = {}
        for i in range(len(o_logs) - 1):
            current = o_logs[i]
            activity = current.status_service or current.status_changeover
            if not activity or activity in SKIP_SERVICE_STATUSES:
                continue
            next_log = o_logs[i + 1]
            t1 = _parse_service_dt(current.created_at)
            t2 = _parse_service_dt(next_log.created_at)
            if not t1 or not t2:
                continue
            delta = (t2 - t1).total_seconds() / 60.0
            if delta > 720:  # 12h safety cap
                delta = 0
            mould = (
                current.mould_number
                or service_mould_map.get(current.mes_activ_service_id)
                or changeover_mould_map.get(current.mes_activ_changeover_id)
            )
            key = (activity, mould)
            activity_minutes[key] = activity_minutes.get(key, 0) + delta
        for (activity, mould), mins in activity_minutes.items():
            mins = round(mins)
            if mins > 0:
                result.setdefault(operator, {})[(activity, mould)] = mins

    return result


def _build_service_label(activity_type: str, mould_number: str = None, mould_product: str = None) -> str:
    if mould_number and mould_product:
        return f"{activity_type} — {mould_number} — {mould_product}"
    if mould_number:
        return f"{activity_type} — {mould_number}"
    return activity_type


@router.get("/service-cards", response_model=ServiceCardResponse, dependencies=[Depends(admin_required)])
async def get_service_cards(target_date: date = Query(..., alias="date"), db: db_dependency = None):
    users = db.query(Users.id, Users.username).all()
    user_map = {u.id: u.username for u in users}
    username_to_id = {u.username: u.id for u in users}
    mould_product_map = {
        m.mould_number: m.product
        for m in db.query(Mould.mould_number, Mould.product).all()
    }

    saved = db.query(AnalyticaService).filter(AnalyticaService.date == target_date).all()
    saved_by_user = {}
    for row in saved:
        saved_by_user.setdefault(row.user_id, []).append(row)

    log_data = _compute_service_from_logs(db, target_date)

    # Map log_data from username keys to user_id keys
    log_by_user = {}
    for username, activities in log_data.items():
        uid = username_to_id.get(username)
        if uid:
            log_by_user[uid] = activities

    workers = []
    all_user_ids = set(saved_by_user.keys()) | set(log_by_user.keys())

    for user_id in sorted(all_user_ids):
        username = user_map.get(user_id, f"User #{user_id}")

        if user_id in saved_by_user:
            entries = [
                ServiceEntry(
                    activity_type=row.activity_type,
                    activity_label=_build_service_label(
                        row.activity_type,
                        row.mould_number,
                        mould_product_map.get(row.mould_number),
                    ),
                    mould_number=row.mould_number,
                    mould_product=mould_product_map.get(row.mould_number),
                    minutes=row.minutes,
                )
                for row in saved_by_user[user_id]
            ]
            source = "saved"
        elif user_id in log_by_user:
            entries = [
                ServiceEntry(
                    activity_type=activity,
                    activity_label=_build_service_label(activity, mould, mould_product_map.get(mould)),
                    mould_number=mould,
                    mould_product=mould_product_map.get(mould),
                    minutes=mins,
                )
                for (activity, mould), mins in log_by_user[user_id].items()
            ]
            source = "logs"
        else:
            continue

        total = sum(e.minutes for e in entries)
        if total > 0:
            workers.append(ServiceCard(
                user_id=user_id,
                username=username,
                source=source,
                entries=entries,
                total_minutes=total,
            ))

    return ServiceCardResponse(date=target_date, workers=workers)


@router.post("/service-cards", dependencies=[Depends(admin_required)])
async def save_service_card(payload: ServiceCardSave, db: db_dependency = None):
    db.query(AnalyticaService).filter(
        AnalyticaService.user_id == payload.user_id,
        AnalyticaService.date == payload.date,
    ).delete()

    for entry in payload.entries:
        if entry.minutes > 0:
            obj = AnalyticaService(
                user_id=payload.user_id,
                date=payload.date,
                activity_type=entry.activity_type,
                mould_number=entry.mould_number,
                minutes=entry.minutes,
            )
            db.add(obj)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not save service card")

    return {"message": "Service card saved", "user_id": payload.user_id, "date": str(payload.date)}


@router.delete("/service-cards", dependencies=[Depends(admin_required)])
async def reset_service_card(
    user_id: int = Query(...),
    target_date: date = Query(..., alias="date"),
    db: db_dependency = None,
):
    deleted = db.query(AnalyticaService).filter(
        AnalyticaService.user_id == user_id,
        AnalyticaService.date == target_date,
    ).delete()

    db.commit()
    return {"message": f"Deleted {deleted} entries", "user_id": user_id, "date": str(target_date)}

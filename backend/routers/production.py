from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import db_dependency
from models.production import (
    MachineGroup,
    MachineStatus,
    OrderType,
    ProductionOrder,
    ProductionTask,
    Workstation,
    Operation,
    OperationLog,
)
from models.user import Users
from routers.auth import user_required, admin_required, superadmin_required
from schemas.production import (
    MachineGroupCreate,
    MachineGroupRead,
    MachineStatusCreate,
    MachineStatusUpdate,
    MachineStatusRead,
    OrderTypeCreate,
    OrderTypeUpdate,
    OrderTypeRead,
    ProductionOrderCreate,
    ProductionOrderUpdate,
    ProductionOrderRead,
    ProductionTaskCreate,
    ProductionTaskUpdate,
    ProductionTaskRead,
    WorkstationCreate,
    WorkstationUpdate,
    WorkstationRead,
    OperationCreate,
    OperationUpdate,
    OperationRead,
    OperationReorderRequest,
    OperationLogCreate,
    OperationLogUpdate,
    OperationLogRead,
)

router = APIRouter(prefix="/production", tags=["production"])


def require_row(db: Session, model, row_id: int, name: str):
    row = db.query(model).filter(model.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return row


def commit_or_409(db: Session, detail: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail)


# Status_no values that represent non-working states (no timer)
_NO_TIMER_NOS = {5, 6, 7}
# Status_no for "Koniec zmiany" (end of shift)
_END_SHIFT_NO = 6


def recalculate_operation_durations(db: Session, operation_id: int) -> None:
    """Recalculate duration_total_min and duration_shift_min from operation logs."""
    logs = (
        db.query(OperationLog)
        .filter(OperationLog.operation_id == operation_id)
        .order_by(OperationLog.created_at.asc())
        .all()
    )
    if not logs:
        return

    # Build status_no lookup
    statuses = {s.id: s.status_no for s in db.query(MachineStatus).all()}

    # Find shift boundary: last "Koniec zmiany" log
    shift_start = None
    for log in reversed(logs):
        if statuses.get(log.status_id) == _END_SHIFT_NO:
            shift_start = log.created_at
            break

    now = datetime.now()
    total_seconds = 0.0
    shift_seconds = 0.0

    for i, log in enumerate(logs):
        sno = statuses.get(log.status_id)
        if sno is None or sno in _NO_TIMER_NOS:
            continue  # non-working status

        # End of this status period = next log or now
        end_time = logs[i + 1].created_at if i + 1 < len(logs) else now
        seg = (end_time - log.created_at).total_seconds()
        total_seconds += seg

        # Shift portion
        if shift_start is not None and end_time <= shift_start:
            continue  # entirely before current shift
        if shift_start is not None:
            effective_start = max(log.created_at, shift_start)
            shift_seconds += (end_time - effective_start).total_seconds()
        else:
            shift_seconds += seg  # no shift boundary -> count all

    op = db.query(Operation).filter(Operation.id == operation_id).first()
    if op:
        op.duration_total_min = round(total_seconds / 60)
        op.duration_shift_min = round(shift_seconds / 60)
        db.commit()


@router.get("/machine-statuses", response_model=List[MachineStatusRead])
async def list_machine_statuses(db: db_dependency):
    return db.query(MachineStatus).order_by(MachineStatus.status_no.asc()).all()


@router.post("/machine-statuses", response_model=MachineStatusRead, dependencies=[Depends(admin_required)])
async def create_machine_status(payload: MachineStatusCreate, db: db_dependency):
    obj = MachineStatus(**payload.model_dump())
    db.add(obj)
    commit_or_409(db, "Machine status already exists")
    db.refresh(obj)
    return obj


@router.put("/machine-statuses/{status_id}", response_model=MachineStatusRead, dependencies=[Depends(admin_required)])
async def update_machine_status(status_id: int, payload: MachineStatusUpdate, db: db_dependency):
    obj = require_row(db, MachineStatus, status_id, "Machine status")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Machine status already exists")
    db.refresh(obj)
    return obj


@router.delete("/machine-statuses/{status_id}", status_code=204, dependencies=[Depends(superadmin_required)])
async def delete_machine_status(status_id: int, db: db_dependency):
    obj = require_row(db, MachineStatus, status_id, "Machine status")
    db.delete(obj)
    commit_or_409(db, "Machine status is used by other records")
    return


# ── Machine Groups ──────────────────────────────────────────────────────────


@router.get("/machine-groups", response_model=List[MachineGroupRead])
async def list_machine_groups(db: db_dependency):
    return db.query(MachineGroup).order_by(MachineGroup.name.asc()).all()


@router.post("/machine-groups", response_model=MachineGroupRead, dependencies=[Depends(superadmin_required)])
async def create_machine_group(payload: MachineGroupCreate, db: db_dependency):
    obj = MachineGroup(**payload.model_dump())
    db.add(obj)
    commit_or_409(db, "Machine group already exists")
    db.refresh(obj)
    return obj


@router.put("/machine-groups/{group_id}", response_model=MachineGroupRead, dependencies=[Depends(superadmin_required)])
async def update_machine_group(group_id: int, payload: MachineGroupCreate, db: db_dependency):
    obj = require_row(db, MachineGroup, group_id, "Machine group")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Machine group already exists")
    db.refresh(obj)
    return obj


@router.delete("/machine-groups/{group_id}", status_code=204, dependencies=[Depends(superadmin_required)])
async def delete_machine_group(group_id: int, db: db_dependency):
    obj = require_row(db, MachineGroup, group_id, "Machine group")
    db.delete(obj)
    commit_or_409(db, "Machine group is used by other records")
    return


@router.get("/order-types", response_model=List[OrderTypeRead])
async def list_order_types(db: db_dependency):
    return db.query(OrderType).order_by(OrderType.code.asc()).all()


@router.post("/order-types", response_model=OrderTypeRead, dependencies=[Depends(superadmin_required)])
async def create_order_type(payload: OrderTypeCreate, db: db_dependency):
    obj = OrderType(**payload.model_dump())
    db.add(obj)
    commit_or_409(db, "Order type already exists")
    db.refresh(obj)
    return obj


@router.put("/order-types/{type_id}", response_model=OrderTypeRead, dependencies=[Depends(superadmin_required)])
async def update_order_type(type_id: int, payload: OrderTypeUpdate, db: db_dependency):
    obj = require_row(db, OrderType, type_id, "Order type")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Order type already exists")
    db.refresh(obj)
    return obj


@router.delete("/order-types/{type_id}", status_code=204, dependencies=[Depends(superadmin_required)])
async def delete_order_type(type_id: int, db: db_dependency):
    obj = require_row(db, OrderType, type_id, "Order type")
    db.delete(obj)
    commit_or_409(db, "Order type is used by orders")
    return


@router.get("/orders", response_model=List[ProductionOrderRead])
async def list_orders(db: db_dependency, order_type_id: Optional[int] = None):
    query = db.query(ProductionOrder)
    if order_type_id is not None:
        query = query.filter(ProductionOrder.order_type_id == order_type_id)
    return query.order_by(ProductionOrder.id.desc()).all()


@router.post("/orders", response_model=ProductionOrderRead, dependencies=[Depends(admin_required)])
async def create_order(payload: ProductionOrderCreate, db: db_dependency):
    require_row(db, OrderType, payload.order_type_id, "Order type")
    obj = ProductionOrder(**payload.model_dump())
    db.add(obj)
    commit_or_409(db, "Order number already exists")
    db.refresh(obj)
    return obj


@router.put("/orders/{order_id}", response_model=ProductionOrderRead, dependencies=[Depends(admin_required)])
async def update_order(order_id: int, payload: ProductionOrderUpdate, db: db_dependency):
    obj = require_row(db, ProductionOrder, order_id, "Order")
    data = payload.model_dump(exclude_unset=True)
    if "order_type_id" in data:
        require_row(db, OrderType, data["order_type_id"], "Order type")
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Order number already exists")
    db.refresh(obj)
    return obj


@router.delete("/orders/{order_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_order(order_id: int, db: db_dependency):
    obj = require_row(db, ProductionOrder, order_id, "Order")
    db.delete(obj)
    commit_or_409(db, "Order is used by tasks")
    return


@router.get("/tasks", response_model=List[ProductionTaskRead])
async def list_tasks(db: db_dependency, order_id: Optional[int] = None):
    query = db.query(ProductionTask)
    if order_id is not None:
        query = query.filter(ProductionTask.order_id == order_id)
    return query.order_by(ProductionTask.id.desc()).all()


@router.post("/tasks", response_model=ProductionTaskRead, dependencies=[Depends(admin_required)])
async def create_task(payload: ProductionTaskCreate, db: db_dependency):
    require_row(db, ProductionOrder, payload.order_id, "Order")
    obj = ProductionTask(**payload.model_dump())
    db.add(obj)
    commit_or_409(db, "Task already exists")
    db.refresh(obj)
    return obj


@router.put("/tasks/{task_id}", response_model=ProductionTaskRead, dependencies=[Depends(admin_required)])
async def update_task(task_id: int, payload: ProductionTaskUpdate, db: db_dependency):
    obj = require_row(db, ProductionTask, task_id, "Task")
    data = payload.model_dump(exclude_unset=True)
    if "order_id" in data:
        require_row(db, ProductionOrder, data["order_id"], "Order")
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Task already exists")
    db.refresh(obj)
    return obj


@router.delete("/tasks/{task_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_task(task_id: int, db: db_dependency):
    obj = require_row(db, ProductionTask, task_id, "Task")
    db.delete(obj)
    commit_or_409(db, "Task is used by operations or workstations")
    return


@router.get("/workstations", response_model=List[WorkstationRead])
async def list_workstations(db: db_dependency, status_id: Optional[int] = None):
    query = db.query(Workstation)
    if status_id is not None:
        query = query.filter(Workstation.status_id == status_id)
    return query.order_by(Workstation.name.asc()).all()


@router.post("/workstations", response_model=WorkstationRead, dependencies=[Depends(superadmin_required)])
async def create_workstation(payload: WorkstationCreate, db: db_dependency):
    data = payload.model_dump()
    if data.get("status_id") is not None:
        require_row(db, MachineStatus, data["status_id"], "Machine status")
    if data.get("current_task_id") is not None:
        require_row(db, ProductionTask, data["current_task_id"], "Task")
    if data.get("current_operation_id") is not None:
        require_row(db, Operation, data["current_operation_id"], "Operation")
    if data.get("user_id") is not None:
        require_row(db, Users, data["user_id"], "User")
    obj = Workstation(**data)
    db.add(obj)
    commit_or_409(db, "Workstation already exists")
    db.refresh(obj)
    return obj


@router.put("/workstations/{workstation_id}", response_model=WorkstationRead, dependencies=[Depends(user_required)])
async def update_workstation(workstation_id: int, payload: WorkstationUpdate, db: db_dependency):
    obj = require_row(db, Workstation, workstation_id, "Workstation")
    data = payload.model_dump(exclude_unset=True)
    if "status_id" in data and data["status_id"] is not None:
        require_row(db, MachineStatus, data["status_id"], "Machine status")
    if "current_task_id" in data and data["current_task_id"] is not None:
        require_row(db, ProductionTask, data["current_task_id"], "Task")
    if "current_operation_id" in data and data["current_operation_id"] is not None:
        require_row(db, Operation, data["current_operation_id"], "Operation")
    if "user_id" in data and data["user_id"] is not None:
        require_row(db, Users, data["user_id"], "User")
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Workstation already exists")
    db.refresh(obj)
    return obj


@router.delete("/workstations/{workstation_id}", status_code=204, dependencies=[Depends(superadmin_required)])
async def delete_workstation(workstation_id: int, db: db_dependency):
    obj = require_row(db, Workstation, workstation_id, "Workstation")
    db.delete(obj)
    commit_or_409(db, "Workstation is used by operations or logs")
    return


@router.get("/operations", response_model=List[OperationRead])
async def list_operations(db: db_dependency, task_id: Optional[int] = None):
    query = db.query(Operation)
    if task_id is not None:
        query = query.filter(Operation.task_id == task_id)
    return query.order_by(Operation.sort_order.asc(), Operation.id.asc()).all()


@router.put("/operations/reorder", dependencies=[Depends(user_required)])
async def reorder_operations(payload: OperationReorderRequest, db: db_dependency):
    for item in payload.items:
        obj = db.query(Operation).filter(Operation.id == item.id).first()
        if obj:
            obj.sort_order = item.sort_order
    db.commit()
    return {"status": "ok"}


@router.post("/operations", response_model=OperationRead, dependencies=[Depends(admin_required)])
async def create_operation(payload: OperationCreate, db: db_dependency):
    data = payload.model_dump()
    require_row(db, ProductionTask, data["task_id"], "Task")
    if data.get("workstation_id") is not None:
        require_row(db, Workstation, data["workstation_id"], "Workstation")
    obj = Operation(**data)
    db.add(obj)
    commit_or_409(db, "Operation already exists")
    db.refresh(obj)
    return obj


@router.put("/operations/{operation_id}", response_model=OperationRead, dependencies=[Depends(admin_required)])
async def update_operation(operation_id: int, payload: OperationUpdate, db: db_dependency):
    obj = require_row(db, Operation, operation_id, "Operation")
    data = payload.model_dump(exclude_unset=True)
    if "task_id" in data:
        require_row(db, ProductionTask, data["task_id"], "Task")
    if "workstation_id" in data and data["workstation_id"] is not None:
        require_row(db, Workstation, data["workstation_id"], "Workstation")
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Operation already exists")
    db.refresh(obj)
    return obj


@router.delete("/operations/{operation_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_operation(operation_id: int, db: db_dependency):
    obj = require_row(db, Operation, operation_id, "Operation")
    db.delete(obj)
    commit_or_409(db, "Operation is used by logs")
    return


@router.post("/operations/{operation_id}/recalculate", response_model=OperationRead, dependencies=[Depends(user_required)])
async def recalculate_operation(operation_id: int, db: db_dependency):
    require_row(db, Operation, operation_id, "Operation")
    recalculate_operation_durations(db, operation_id)
    db.refresh(require_row(db, Operation, operation_id, "Operation"))
    return require_row(db, Operation, operation_id, "Operation")


@router.get("/logs", response_model=List[OperationLogRead])
async def list_logs(db: db_dependency, operation_id: Optional[int] = None):
    query = db.query(OperationLog)
    if operation_id is not None:
        query = query.filter(OperationLog.operation_id == operation_id)
    return query.order_by(OperationLog.id.desc()).all()


@router.post("/logs", response_model=OperationLogRead, dependencies=[Depends(user_required)])
async def create_log(payload: OperationLogCreate, db: db_dependency):
    data = payload.model_dump()
    if data.get("created_at") is None:
        data["created_at"] = datetime.now()
    require_row(db, Operation, data["operation_id"], "Operation")
    if data.get("status_id") is not None:
        require_row(db, MachineStatus, data["status_id"], "Machine status")
    if data.get("workstation_id") is not None:
        require_row(db, Workstation, data["workstation_id"], "Workstation")
    if data.get("user_id") is not None:
        require_row(db, Users, data["user_id"], "User")
    obj = OperationLog(**data)
    db.add(obj)
    commit_or_409(db, "Log already exists")
    db.refresh(obj)
    recalculate_operation_durations(db, data["operation_id"])
    return obj


@router.put("/logs/{log_id}", response_model=OperationLogRead, dependencies=[Depends(admin_required)])
async def update_log(log_id: int, payload: OperationLogUpdate, db: db_dependency):
    obj = require_row(db, OperationLog, log_id, "Log")
    data = payload.model_dump(exclude_unset=True)
    if "status_id" in data and data["status_id"] is not None:
        require_row(db, MachineStatus, data["status_id"], "Machine status")
    if "workstation_id" in data and data["workstation_id"] is not None:
        require_row(db, Workstation, data["workstation_id"], "Workstation")
    if "user_id" in data and data["user_id"] is not None:
        require_row(db, Users, data["user_id"], "User")
    for key, value in data.items():
        setattr(obj, key, value)
    commit_or_409(db, "Log already exists")
    db.refresh(obj)
    return obj


@router.delete("/logs/{log_id}", status_code=204, dependencies=[Depends(admin_required)])
async def delete_log(log_id: int, db: db_dependency):
    obj = require_row(db, OperationLog, log_id, "Log")
    db.delete(obj)
    commit_or_409(db, "Log could not be deleted")
    return


@router.get("/users", dependencies=[Depends(user_required)])
async def list_users(db: db_dependency):
    rows = db.query(Users.id, Users.username).all()
    return [{"id": r.id, "username": r.username} for r in rows]

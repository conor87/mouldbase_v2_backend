from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import db_dependency
from models.production import (
    MachineStatus,
    OrderType,
    ProductionOrder,
    ProductionTask,
    Workstation,
    Operation,
    OperationLog,
)
from models.user import Users
from routers.auth import admin_required, superadmin_required
from schemas.production import (
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


@router.get("/machine-statuses", response_model=List[MachineStatusRead])
async def list_machine_statuses(db: db_dependency):
    return db.query(MachineStatus).order_by(MachineStatus.status_no.asc()).all()


@router.post("/machine-statuses", response_model=MachineStatusRead, dependencies=[Depends(superadmin_required)])
async def create_machine_status(payload: MachineStatusCreate, db: db_dependency):
    obj = MachineStatus(**payload.model_dump())
    db.add(obj)
    commit_or_409(db, "Machine status already exists")
    db.refresh(obj)
    return obj


@router.put("/machine-statuses/{status_id}", response_model=MachineStatusRead, dependencies=[Depends(superadmin_required)])
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
    if data.get("user_id") is not None:
        require_row(db, Users, data["user_id"], "User")
    obj = Workstation(**data)
    db.add(obj)
    commit_or_409(db, "Workstation already exists")
    db.refresh(obj)
    return obj


@router.put("/workstations/{workstation_id}", response_model=WorkstationRead, dependencies=[Depends(superadmin_required)])
async def update_workstation(workstation_id: int, payload: WorkstationUpdate, db: db_dependency):
    obj = require_row(db, Workstation, workstation_id, "Workstation")
    data = payload.model_dump(exclude_unset=True)
    if "status_id" in data and data["status_id"] is not None:
        require_row(db, MachineStatus, data["status_id"], "Machine status")
    if "current_task_id" in data and data["current_task_id"] is not None:
        require_row(db, ProductionTask, data["current_task_id"], "Task")
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
    return query.order_by(Operation.id.desc()).all()


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


@router.get("/logs", response_model=List[OperationLogRead])
async def list_logs(db: db_dependency, operation_id: Optional[int] = None):
    query = db.query(OperationLog)
    if operation_id is not None:
        query = query.filter(OperationLog.operation_id == operation_id)
    return query.order_by(OperationLog.id.desc()).all()


@router.post("/logs", response_model=OperationLogRead, dependencies=[Depends(admin_required)])
async def create_log(payload: OperationLogCreate, db: db_dependency):
    data = payload.model_dump()
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

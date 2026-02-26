from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class MachineStatusBase(BaseModel):
    status_no: int
    name: str
    color: Optional[str] = None


class MachineStatusCreate(MachineStatusBase):
    pass


class MachineStatusUpdate(BaseModel):
    status_no: Optional[int] = None
    name: Optional[str] = None
    color: Optional[str] = None


class MachineStatusRead(MachineStatusBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OrderTypeBase(BaseModel):
    code: str
    name: str


class OrderTypeCreate(OrderTypeBase):
    pass


class OrderTypeUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None


class OrderTypeRead(OrderTypeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProductionOrderBase(BaseModel):
    order_number: str
    order_type_id: int
    is_done: bool = False
    team: Optional[str] = None
    product_name: Optional[str] = None


class ProductionOrderCreate(ProductionOrderBase):
    pass


class ProductionOrderUpdate(BaseModel):
    order_number: Optional[str] = None
    order_type_id: Optional[int] = None
    is_done: Optional[bool] = None
    team: Optional[str] = None
    product_name: Optional[str] = None


class ProductionOrderRead(ProductionOrderBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProductionTaskBase(BaseModel):
    order_id: int
    detail_number: str
    detail_name: str
    is_done: bool = False
    quantity: Optional[int] = None


class ProductionTaskCreate(ProductionTaskBase):
    pass


class ProductionTaskUpdate(BaseModel):
    order_id: Optional[int] = None
    detail_number: Optional[str] = None
    detail_name: Optional[str] = None
    is_done: Optional[bool] = None
    quantity: Optional[int] = None


class ProductionTaskRead(ProductionTaskBase):
    model_config = ConfigDict(from_attributes=True)
    id: int



class MachineGroupBase(BaseModel):
    name: str


class MachineGroupCreate(MachineGroupBase):
    pass


class MachineGroupRead(MachineGroupBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class WorkstationBase(BaseModel):
    name: str
    cost_center: Optional[str] = None
    status_id: Optional[int] = None
    current_task_id: Optional[int] = None
    current_operation_id: Optional[int] = None
    user_id: Optional[int] = None
    machine_group_id: Optional[int] = None


class WorkstationCreate(WorkstationBase):
    pass


class WorkstationUpdate(BaseModel):
    name: Optional[str] = None
    cost_center: Optional[str] = None
    status_id: Optional[int] = None
    current_task_id: Optional[int] = None
    current_operation_id: Optional[int] = None
    user_id: Optional[int] = None
    machine_group_id: Optional[int] = None


class WorkstationRead(WorkstationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    machine_group: Optional[MachineGroupRead] = None


class OperationBase(BaseModel):
    task_id: int
    operation_no: int
    description: str
    created_at: Optional[datetime] = None
    suggested_duration_min: Optional[int] = None
    is_done: bool = False
    is_released: bool = False
    is_started: bool = False
    duration_total_min: int = 0
    duration_shift_min: int = 0
    sort_order: int = 999
    workstation_id: Optional[int] = None


class OperationCreate(OperationBase):
    pass


class OperationUpdate(BaseModel):
    task_id: Optional[int] = None
    operation_no: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    suggested_duration_min: Optional[int] = None
    is_done: Optional[bool] = None
    is_released: Optional[bool] = None
    is_started: Optional[bool] = None
    duration_total_min: Optional[int] = None
    duration_shift_min: Optional[int] = None
    sort_order: Optional[int] = None
    workstation_id: Optional[int] = None


class OperationRead(OperationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OperationReorderItem(BaseModel):
    id: int
    sort_order: int


class OperationReorderRequest(BaseModel):
    items: List[OperationReorderItem]


class OperationLogBase(BaseModel):
    operation_id: int
    status_id: Optional[int] = None
    workstation_id: Optional[int] = None
    user_id: Optional[int] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class OperationLogCreate(OperationLogBase):
    pass


class OperationLogUpdate(BaseModel):
    status_id: Optional[int] = None
    workstation_id: Optional[int] = None
    user_id: Optional[int] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class OperationLogRead(OperationLogBase):
    model_config = ConfigDict(from_attributes=True)
    id: int

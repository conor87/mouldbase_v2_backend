from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date, datetime


class WorkerEntry(BaseModel):
    workstation_id: int
    workstation_name: Optional[str] = None
    order_number: Optional[str] = None
    minutes: int


class WorkerCard(BaseModel):
    user_id: int
    username: str
    source: str  # "saved" or "logs"
    entries: List[WorkerEntry]
    total_minutes: int


class WorkerCardSave(BaseModel):
    user_id: int
    date: date
    entries: List[WorkerEntry]


class WorkerCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    workers: List[WorkerCard]


# --- Machine analytics ---

class MachineEntry(BaseModel):
    operation_id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    operation_label: Optional[str] = None
    order_number: Optional[str] = None
    minutes: int


class MachineCard(BaseModel):
    workstation_id: int
    workstation_name: str
    source: str  # "saved" or "logs"
    entries: List[MachineEntry]
    total_minutes: int


class MachineCardSave(BaseModel):
    workstation_id: int
    date: date
    entries: List[MachineEntry]


class MachineCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    machines: List[MachineCard]


# --- Service analytics ---

class ServiceEntry(BaseModel):
    activity_type: str
    activity_label: Optional[str] = None
    mould_number: Optional[str] = None
    minutes: int


class ServiceCard(BaseModel):
    user_id: int
    username: str
    source: str  # "saved" or "logs"
    entries: List[ServiceEntry]
    total_minutes: int


class ServiceCardSave(BaseModel):
    user_id: int
    date: date
    entries: List[ServiceEntry]


class ServiceCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    workers: List[ServiceCard]

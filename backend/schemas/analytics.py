from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date, datetime


class WorkerEntry(BaseModel):
    workstation_id: int
    workstation_name: Optional[str] = None
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

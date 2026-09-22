from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class PreparationTpm(BaseModel):
    id: int
    status: int
    tpm_time_type: int
    description: Optional[str] = None
    created: Optional[date] = None


class PreparationChangeover(BaseModel):
    status: str
    changeover_id: Optional[int] = None
    from_mould_id: Optional[int] = None
    to_mould_id: Optional[int] = None
    needed_date: Optional[datetime] = None


class PreparationAction(BaseModel):
    type: str
    description: str
    record_id: Optional[int] = None


class ProductionPreparationRead(BaseModel):
    production_id: str
    required_mould_id: Optional[int] = None
    required_mould_number: str
    current_mould_id: Optional[int] = None
    current_mould_number: Optional[str] = None
    product: Optional[str] = None
    product_code: Optional[str] = None
    planned_start: datetime
    planned_end: Optional[datetime] = None
    production_type: Optional[int] = None
    readiness: str
    priority: str
    changeover_required: bool
    changeover: PreparationChangeover
    open_tpms: list[PreparationTpm] = Field(default_factory=list)
    actions: list[PreparationAction] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)

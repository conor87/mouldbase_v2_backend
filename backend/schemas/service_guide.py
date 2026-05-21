from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ServiceGuideStepBase(BaseModel):
    lp: int = 1
    fault: Optional[str] = None
    confirmed_by: Optional[str] = None
    repair: Optional[str] = None
    performed_by: Optional[str] = None
    is_done: bool = False


class ServiceGuideStepCreate(ServiceGuideStepBase):
    pass


class ServiceGuideStepUpdate(BaseModel):
    lp: Optional[int] = None
    fault: Optional[str] = None
    confirmed_by: Optional[str] = None
    repair: Optional[str] = None
    performed_by: Optional[str] = None
    is_done: Optional[bool] = None


class ServiceGuideStepRead(ServiceGuideStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guide_id: int
    created_at: datetime
    updated_at: datetime


class ServiceGuideBase(BaseModel):
    mould_id: Optional[int] = None
    guide_number: str
    product_name: str = ""
    review_date: Optional[date] = None
    review_reason: Optional[str] = None


class ServiceGuideCreate(ServiceGuideBase):
    pass


class ServiceGuideUpdate(BaseModel):
    mould_id: Optional[int] = None
    guide_number: Optional[str] = None
    product_name: Optional[str] = None
    review_date: Optional[date] = None
    review_reason: Optional[str] = None
    status: Optional[str] = None


class ServiceGuideRead(ServiceGuideBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    steps: list[ServiceGuideStepRead] = Field(default_factory=list)

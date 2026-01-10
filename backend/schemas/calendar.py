# schemas/calendar.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CalendarBase(BaseModel):
    mould_id: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    comment: Optional[str] = None
    is_active: bool = True
    created_by: Optional[str] = None


class CalendarRead(CalendarBase):
    id: int
    created: datetime
    updated: datetime

    class Config:
        model_config = {"from_attributes": True}

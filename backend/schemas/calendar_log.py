# schemas/calendar_log.py
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class CalendarLogRead(BaseModel):
    id: int
    calendar_entry_id: int
    action: str
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    updated_by: Optional[str] = None
    created: datetime

    class Config:
        model_config = {"from_attributes": True}

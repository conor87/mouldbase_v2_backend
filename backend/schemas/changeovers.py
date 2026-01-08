# schemas/changeovers.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChangeoverBase(BaseModel):
    from_mould_id: int
    to_mould_id: int
    available_date: Optional[datetime] = None
    needed_date: Optional[datetime] = None
    czy_wykonano: bool = False
    updated_by: Optional[str] = None


class ChangeoverCreate(ChangeoverBase):
    pass


class ChangeoverUpdate(BaseModel):
    from_mould_id: Optional[int] = None
    to_mould_id: Optional[int] = None
    available_date: Optional[datetime] = None
    needed_date: Optional[datetime] = None
    czy_wykonano: Optional[bool] = None
    updated_by: Optional[str] = None


class ChangeoverRead(ChangeoverBase):
    id: int
    created: datetime
    updated: datetime

    class Config:
        model_config = {"from_attributes": True}

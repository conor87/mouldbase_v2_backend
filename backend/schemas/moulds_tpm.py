# schemas/moulds_tpm.py
from datetime import date
from typing import Optional
from pydantic import BaseModel

class MouldsTpmBase(BaseModel):
    sv: Optional[int] = 0
    tpm_time_type: int = 0
    opis_zgloszenia: Optional[str] = None
    ido: Optional[int] = 0
    status: int = 0
    changed: Optional[date] = None
    author: Optional[str] = None

class MouldsTpmCreate(MouldsTpmBase):
    mould_id: int

class MouldsTpmUpdate(MouldsTpmBase):
    pass

class MouldsTpmRead(MouldsTpmBase):
    id: int
    mould_id: int
    created: date
    extra_photo_1: Optional[str] = None
    extra_photo_2: Optional[str] = None

    class Config:
        model_config = {"from_attributes": True}

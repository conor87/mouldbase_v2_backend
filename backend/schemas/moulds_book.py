# schemas/moulds_tpm.py
from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict

class MouldsBookBase(BaseModel):
    sv: Optional[int] = 0
    czas_trwania: Optional[int] = 0
    czas_wylaczenia: Optional[int] = 0
    tpm_type: int = 0
    opis_zgloszenia: Optional[str] = None
    ido: Optional[int] = 0

class MouldsBookCreate(MouldsBookBase):
    mould_id: int

class MouldsBookUpdate(MouldsBookBase):
    pass

class MouldsBookRead(MouldsBookBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mould_id: int
    created: date
    czas_trwania: Optional[int] = 0
    czas_wylaczenia: Optional[int] = 0
    extra_photo_1: Optional[str] = None
    extra_photo_2: Optional[str] = None
    opis_zgloszenia: Optional[str] = None

# schemas/mould.py
from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class MouldBase(BaseModel):
    product: Optional[str] = ""
    released: Optional[date] = None
    num_of_cavities: Optional[str] = None
    company: Optional[str] = None
    czy_przezbrajalna: Optional[bool] = False
    tool_weight: Optional[str] = None
    total_cycles: Optional[int] = 0
    to_maint_cycles: Optional[int] = 0
    from_maint_cycles: Optional[int] = 0
    place: Optional[int] = 0
    status: Optional[int] = 0
    notes: Optional[str] = None


class MouldCreate(MouldBase):
    mould_number: str

    @field_validator("mould_number")
    @classmethod
    def uppercase_mould_number(cls, v: str) -> str:
        return v.strip().upper()


class MouldUpdate(MouldBase):
    mould_number: Optional[str] = None

    @field_validator("mould_number")
    @classmethod
    def uppercase_mould_number(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v


class MouldRead(MouldBase):
    # ✅ kluczowe dla ORM (SQLAlchemy)
    model_config = ConfigDict(from_attributes=True)

    id: int
    mould_number: str

    mould_photo: Optional[str] = None
    product_photo: Optional[str] = None
    hot_system_photo: Optional[str] = None
    extra_photo_1: Optional[str] = None
    extra_photo_2: Optional[str] = None
    extra_photo_3: Optional[str] = None
    extra_photo_4: Optional[str] = None
    extra_photo_5: Optional[str] = None


class MouldReadWithTpm(MouldRead):
    has_open_tpm: bool = False

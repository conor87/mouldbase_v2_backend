from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class CompanyBase(BaseModel):
    name: str
    address: str
    zip_code: str
    city: str
    country: str
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    is_active: bool = True
    
    
class CompanyModel(CompanyBase):
    id: int

    class Config:
        from_attributes = True
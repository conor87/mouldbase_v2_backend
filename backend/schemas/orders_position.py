
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class Orders_position_Base(BaseModel):
    amount: float
    category: str
    description: str
    is_income: bool
    date: str  # Ideally use date type, simplified here for brevity
    company_id: Optional[int] = None
    
    
class Orders_position_Model(Orders_position_Base):
    id: int
    company_id: Optional[int] = None

    class Config:
        from_attributes = True
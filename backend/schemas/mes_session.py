from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MesSessionLogCreate(BaseModel):
    user_id: int
    username: str
    action: str
    created_at: Optional[datetime] = None


class MesSessionLogRead(MesSessionLogCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)

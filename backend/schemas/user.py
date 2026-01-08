from typing import Optional
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None

class UserCreate(UserBase):
    password: str

class UserModel(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

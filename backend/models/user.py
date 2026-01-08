#models/user.py
from db.database import Base
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import deferred

class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    #hashed_password=Column(String)
    hashed_password=deferred(Column(String(2000)))
    author = Column(String, index=True)
    role = Column(String, default="user", nullable=False)  # "user" | "admin" | "superadmin"

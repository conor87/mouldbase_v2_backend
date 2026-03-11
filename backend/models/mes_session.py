from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from db.database import Base


class MesSessionLog(Base):
    __tablename__ = "mes_session_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=False)
    action = Column(String(20), nullable=False)  # "login" / "logout"
    created_at = Column(DateTime, nullable=False, server_default=func.now())

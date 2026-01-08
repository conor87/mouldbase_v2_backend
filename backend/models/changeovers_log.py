# models/changeovers_log.py
from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from db.database import Base


class ChangeoverLog(Base):
    __tablename__ = "changeovers_log"

    id = Column(Integer, primary_key=True, index=True)

    changeover_id = Column(Integer, ForeignKey("changeovers.id", ondelete="CASCADE"), nullable=False)

    action = Column(Text, nullable=False)  # CREATE / UPDATE / TOGGLE_DONE / DELETE

    # snapshoty JSON
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)

    updated_by = Column(Text, nullable=True)

    created = Column(DateTime, nullable=False, server_default=func.now())

    # ✅ RELACJA W DRUGĄ STRONĘ (bez backref)
    changeover = relationship("Changeover", back_populates="logs")

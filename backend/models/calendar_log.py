# models/calendar_log.py
from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from db.database import Base


class CalendarLog(Base):
    __tablename__ = "calendar_log"

    id = Column(Integer, primary_key=True, index=True)

    calendar_entry_id = Column(Integer, ForeignKey("calendar_entries.id", ondelete="CASCADE"), nullable=False)

    action = Column(Text, nullable=False)  # CREATE / UPDATE / TOGGLE_STATUS / DELETE

    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)

    updated_by = Column(Text, nullable=True)

    created = Column(DateTime, nullable=False, server_default=func.now())

    calendar_entry = relationship("CalendarEntry", back_populates="logs")

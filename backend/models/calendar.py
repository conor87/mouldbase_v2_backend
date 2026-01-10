# models/calendar.py
from sqlalchemy import Column, Integer, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"

    id = Column(Integer, primary_key=True, index=True)
    mould_id = Column(Integer, ForeignKey("moulds.id", ondelete="CASCADE"), nullable=False)

    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    comment = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Text, nullable=True)

    created = Column(DateTime, nullable=False, server_default=func.now())
    updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    mould = relationship("Mould", back_populates="calendar_entries")
    logs = relationship(
        "CalendarLog",
        back_populates="calendar_entry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(CalendarLog.id)",
    )

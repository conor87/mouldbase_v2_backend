# models/changeovers.py
from sqlalchemy import Column, Integer, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base


class Changeover(Base):
    __tablename__ = "changeovers"

    id = Column(Integer, primary_key=True, index=True)

    from_mould_id = Column(Integer, ForeignKey("moulds.id", ondelete="CASCADE"), nullable=False)
    to_mould_id = Column(Integer, ForeignKey("moulds.id", ondelete="CASCADE"), nullable=False)

    available_date = Column(DateTime, nullable=True)
    needed_date = Column(DateTime, nullable=True)

    czy_wykonano = Column(Boolean, nullable=False, default=False)
    updated_by = Column(Text, nullable=True)

    created = Column(DateTime, nullable=False, server_default=func.now())
    updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    from_mould = relationship("Mould", foreign_keys=[from_mould_id])
    to_mould = relationship("Mould", foreign_keys=[to_mould_id])

    # ✅ RELACJA DO LOGÓW (bez backref)
    logs = relationship(
        "ChangeoverLog",
        back_populates="changeover",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(ChangeoverLog.id)",
    )

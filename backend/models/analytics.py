from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.database import Base


class AnalyticaWorkers(Base):
    __tablename__ = "analytica_workers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    workstation_id = Column(Integer, ForeignKey("workstations.id", ondelete="CASCADE"), nullable=False)
    minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", "workstation_id", name="uq_user_date_workstation"),
    )


class AnalyticaMachines(Base):
    __tablename__ = "analytica_machines"

    id = Column(Integer, primary_key=True, index=True)
    workstation_id = Column(Integer, ForeignKey("workstations.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    operation_id = Column(Integer, ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)
    minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("workstation_id", "date", "operation_id", name="uq_ws_date_operation"),
    )

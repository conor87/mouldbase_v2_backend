from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.database import Base


class AnalyticaWorkers(Base):
    __tablename__ = "analytica_workers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    workstation_id = Column(Integer, ForeignKey("workstations.id", ondelete="CASCADE"), nullable=False)
    order_number = Column(String(64), nullable=True)
    minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", "workstation_id", "order_number", name="uq_user_date_ws_order"),
    )


class AnalyticaMachines(Base):
    __tablename__ = "analytica_machines"

    id = Column(Integer, primary_key=True, index=True)
    workstation_id = Column(Integer, ForeignKey("workstations.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    operation_id = Column(Integer, ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("workstation_id", "date", "operation_id", "user_id", name="uq_ws_date_op_user"),
    )


class AnalyticaService(Base):
    __tablename__ = "analytica_service"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    activity_type = Column(String(100), nullable=False)
    mould_number = Column(String(50), nullable=True)
    minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", "activity_type", "mould_number", name="uq_user_date_activity_mould"),
    )

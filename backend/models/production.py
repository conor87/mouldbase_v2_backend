from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.database import Base


class MachineStatus(Base):
    __tablename__ = "machine_statuses"

    id = Column(Integer, primary_key=True, index=True)
    status_no = Column(Integer, nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    color = Column(String(30), nullable=True)

    workstations = relationship("Workstation", back_populates="status")
    operation_logs = relationship("OperationLog", back_populates="status")


class MachineGroup(Base):
    __tablename__ = "machine_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)

    workstations = relationship("Workstation", back_populates="machine_group")


class OrderType(Base):
    __tablename__ = "order_types"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)

    orders = relationship("ProductionOrder", back_populates="order_type")


class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(64), nullable=False, unique=True, index=True)
    order_type_id = Column(Integer, ForeignKey("order_types.id"), nullable=False)
    is_done = Column(Boolean, nullable=False, default=False)
    team = Column(String(100), nullable=True)
    product_name = Column(String(100), nullable=True)

    order_type = relationship("OrderType", back_populates="orders")
    tasks = relationship("ProductionTask", back_populates="order", cascade="all, delete-orphan")


class ProductionTask(Base):
    __tablename__ = "production_tasks"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False)
    detail_number = Column(String(100), nullable=False)
    detail_name = Column(String(100), nullable=False)
    is_done = Column(Boolean, nullable=False, default=False)
    quantity = Column(Integer, nullable=True)

    order = relationship("ProductionOrder", back_populates="tasks")
    operations = relationship("Operation", back_populates="task", cascade="all, delete-orphan")
    current_on_workstations = relationship("Workstation", back_populates="current_task")


class Workstation(Base):
    __tablename__ = "workstations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    cost_center = Column(String(50), nullable=True)
    status_id = Column(Integer, ForeignKey("machine_statuses.id"), nullable=True)
    current_task_id = Column(Integer, ForeignKey("production_tasks.id", ondelete="SET NULL"), nullable=True)
    current_operation_id = Column(Integer, ForeignKey("operations.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    machine_group_id = Column(Integer, ForeignKey("machine_groups.id"), nullable=True)

    status = relationship("MachineStatus", back_populates="workstations")
    machine_group = relationship("MachineGroup", back_populates="workstations")
    current_task = relationship("ProductionTask", back_populates="current_on_workstations")
    current_operation = relationship("Operation", foreign_keys=[current_operation_id])
    operations = relationship("Operation", back_populates="workstation", foreign_keys="[Operation.workstation_id]")
    logs = relationship("OperationLog", back_populates="workstation")


class Operation(Base):
    __tablename__ = "operations"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("production_tasks.id", ondelete="CASCADE"), nullable=False)
    operation_no = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    suggested_duration_min = Column(Integer, nullable=True)
    is_done = Column(Boolean, nullable=False, default=False)
    is_released = Column(Boolean, nullable=False, default=False)
    is_started = Column(Boolean, nullable=False, default=False)
    duration_total_min = Column(Integer, nullable=False, default=0)
    duration_shift_min = Column(Integer, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=999)
    workstation_id = Column(Integer, ForeignKey("workstations.id", ondelete="SET NULL"), nullable=True)

    task = relationship("ProductionTask", back_populates="operations")
    workstation = relationship("Workstation", back_populates="operations", foreign_keys=[workstation_id])
    logs = relationship("OperationLog", back_populates="operation", cascade="all, delete-orphan")


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(Integer, ForeignKey("operations.id", ondelete="CASCADE"), nullable=False)
    status_id = Column(Integer, ForeignKey("machine_statuses.id", ondelete="SET NULL"), nullable=True)
    workstation_id = Column(Integer, ForeignKey("workstations.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    operation = relationship("Operation", back_populates="logs")
    status = relationship("MachineStatus", back_populates="operation_logs")
    workstation = relationship("Workstation", back_populates="logs")

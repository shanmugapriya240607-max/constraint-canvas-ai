"""Planning data only: no schedules, assignments, or solver state."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float, ForeignKey, ForeignKeyConstraint,
    Index, Integer, JSON, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Store uniform UTC in SQLite; return aware UTC timestamps on every read."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware datetime required")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Plan(Timestamps, Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("planning_end > planning_start", name="ck_plan_window"),
        CheckConstraint("status IN ('draft','ready','solved','infeasible','archived')", name="ck_plan_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    planning_start: Mapped[datetime] = mapped_column(UTCDateTime())
    planning_end: Mapped[datetime] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")


class Resource(Timestamps, Base):
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("plan_id", "name_key", name="uq_resource_plan_name"),
        UniqueConstraint("id", "plan_id", name="uq_resource_id_plan"),
        CheckConstraint("capacity > 0", name="ck_resource_capacity"),
        CheckConstraint("cost_per_hour IS NULL OR cost_per_hour >= 0", name="ck_resource_cost"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    # Case-folded name is internal and excluded from public response models.
    name_key: Mapped[str] = mapped_column(String(300))
    resource_type: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(Integer)
    cost_per_hour: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ResourceAvailability(Base):
    __tablename__ = "resource_availability"
    __table_args__ = (
        CheckConstraint("available_until > available_from", name="ck_availability_window"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    available_from: Mapped[datetime] = mapped_column(UTCDateTime())
    available_until: Mapped[datetime] = mapped_column(UTCDateTime())


class Task(Timestamps, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("id", "plan_id", name="uq_task_id_plan"),
        CheckConstraint("duration_minutes > 0", name="ck_task_duration"),
        CheckConstraint("priority IN ('low','medium','high','critical')", name="ck_task_priority"),
        CheckConstraint("deadline IS NULL OR earliest_start IS NULL OR deadline > earliest_start", name="ck_task_window"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(20), default="medium", server_default="medium")
    earliest_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    deadline: Mapped[datetime | None] = mapped_column(UTCDateTime())


class TaskRequirement(Base):
    __tablename__ = "task_requirements"
    __table_args__ = (
        ForeignKeyConstraint(["task_id", "plan_id"], ["tasks.id", "tasks.plan_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["required_resource_id", "plan_id"], ["resources.id", "resources.plan_id"], ondelete="CASCADE"),
        CheckConstraint("quantity > 0", name="ck_requirement_quantity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    plan_id: Mapped[int] = mapped_column(Integer, index=True)
    resource_type: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    required_resource_id: Mapped[int | None] = mapped_column(Integer, index=True)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(["before_task_id", "plan_id"], ["tasks.id", "tasks.plan_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["after_task_id", "plan_id"], ["tasks.id", "tasks.plan_id"], ondelete="CASCADE"),
        UniqueConstraint("plan_id", "before_task_id", "after_task_id", name="uq_dependency"),
        CheckConstraint("before_task_id != after_task_id", name="ck_dependency_not_self"),
        Index("ix_dependency_after_task", "after_task_id"),
        Index("ix_dependency_before_task", "before_task_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    before_task_id: Mapped[int] = mapped_column(Integer)
    after_task_id: Mapped[int] = mapped_column(Integer)


class ConstraintRule(Timestamps, Base):
    __tablename__ = "constraint_rules"
    __table_args__ = (
        CheckConstraint("constraint_type IN ('deadline','dependency','resource_capacity','availability','max_work_hours','preferred_resource','preferred_time','custom')", name="ck_constraint_type"),
        CheckConstraint("hardness IN ('hard','soft')", name="ck_constraint_hardness"),
        CheckConstraint("source IN ('manual','ai','memory','system')", name="ck_constraint_source"),
        CheckConstraint("weight IS NULL OR weight > 0", name="ck_constraint_weight"),
        CheckConstraint("hardness != 'soft' OR weight IS NOT NULL", name="ck_soft_weight_required"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    constraint_type: Mapped[str] = mapped_column(String(40))
    hardness: Mapped[str] = mapped_column(String(10), default="hard")
    weight: Mapped[float | None] = mapped_column(Float)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(10), default="manual")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

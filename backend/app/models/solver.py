"""Append-only solve results; planning inputs remain in the Phase 3 tables."""
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.planning import UTCDateTime, utcnow


class SolverRun(Base):
    __tablename__ = "solver_runs"
    __table_args__ = (
        CheckConstraint("solver_status IN ('optimal','feasible','infeasible','unknown')", name="ck_solver_run_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    solver_status: Mapped[str] = mapped_column(String(20))
    makespan_minutes: Mapped[int | None]
    solve_duration_ms: Mapped[float] = mapped_column(Float)
    solver_version: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

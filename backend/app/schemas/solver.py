"""Public solve/history responses and explicitly allowlisted constraint parameters."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.planning import Timestamp


class SolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_solve_seconds: float = Field(default=10, gt=0, le=30, allow_inf_nan=False)


class AssignedResource(BaseModel):
    resource_id: int
    name: str
    resource_type: str
    units: int


class ScheduledTask(BaseModel):
    task_id: int
    task_name: str
    start_offset_minutes: int
    end_offset_minutes: int
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    priority: str
    assigned_resources: list[AssignedResource]


class SolveObjective(BaseModel):
    makespan_minutes: int
    weighted_priority_completion: int
    soft_penalty_scaled: int


class SolveMetrics(BaseModel):
    task_count: int
    scheduled_task_count: int
    planning_horizon_minutes: int
    makespan_minutes: int | None
    solver_wall_time_ms: float


class SolveResponse(BaseModel):
    status: Literal["optimal", "feasible", "infeasible", "unknown"]
    plan_id: int
    run_id: int | None = None
    objective: SolveObjective | None = None
    schedule: list[ScheduledTask]
    metrics: SolveMetrics
    warnings: list[str]


class SolverRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plan_id: int
    solver_status: str
    makespan_minutes: int | None
    solve_duration_ms: float
    solver_version: str
    created_at: datetime


class SolverRunDetail(SolverRunSummary):
    result: SolveResponse


ID = Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]


class RuleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeadlineRule(RuleParameters):
    task_id: ID
    deadline: Timestamp


class DependencyRule(RuleParameters):
    before_task_id: ID
    after_task_id: ID


class CapacityRule(RuleParameters):
    resource_id: ID
    capacity: int = Field(strict=True, ge=0, le=1000)


class AvailabilityRule(RuleParameters):
    resource_id: ID
    available_from: Timestamp
    available_until: Timestamp

    @model_validator(mode="after")
    def valid_window(self):
        if self.available_until <= self.available_from:
            raise ValueError("available_until must be later than available_from")
        return self


class MaxWorkRule(RuleParameters):
    resource_id: ID
    max_hours: Decimal = Field(gt=0, le=1000000, allow_inf_nan=False, decimal_places=6)


class PreferredResourceRule(RuleParameters):
    task_id: ID
    resource_id: ID


class PreferredTimeRule(RuleParameters):
    task_id: ID
    preferred_before: Timestamp

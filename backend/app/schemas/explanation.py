"""Deterministic explanations of persisted solver runs."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from app.schemas.solver import SolveObjective


class ExplanationReason(BaseModel):
    kind: Literal["dependency", "earliest_start", "resource_availability",
                  "specific_resource", "resource_capacity", "deadline", "priority", "soft_preference"]
    message: str
    related_task_ids: list[int] = Field(default_factory=list)
    resource_ids: list[int] = Field(default_factory=list)
    satisfied: bool | None = None


class TaskExplanation(BaseModel):
    task_id: int
    task_name: str
    start_time: datetime
    end_time: datetime
    reasons: list[ExplanationReason]


class PlanExplanation(BaseModel):
    plan_id: int
    run_id: int
    status: Literal["optimal", "feasible", "infeasible", "unknown"]
    summary: str
    basis: str = "Latest saved solver run and its input snapshot; current plan edits are not included."
    objective_explanation: list[str]
    objective: SolveObjective | None = None
    tasks: list[TaskExplanation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    analysis_url: str

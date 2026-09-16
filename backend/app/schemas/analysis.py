from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Issue(BaseModel):
    type: str
    severity: Literal["warning", "critical"]
    task_id: int | None = None
    message: str
    required: int | None = None
    available: int | None = None


class RecoveryOption(BaseModel):
    title: str
    explanation: str
    changes_required: str | None = None
    affected_entities: list[int | str] | None = None
    estimated_impact: str | None = None


class Risk(BaseModel):
    task_id: int | None = None
    message: str


class Bottleneck(BaseModel):
    type: Literal["resource", "task", "other"]
    resource_id: int | None = None
    task_id: int | None = None
    name: str | None = None
    utilization_percent: float | None = None
    reason: str


class HealthFactor(BaseModel):
    name: str
    impact: int
    reason: str


class PlanHealth(BaseModel):
    score: int
    grade: Literal["good", "fair", "poor", "critical"]
    factors: list[HealthFactor]


class PlanAnalysisResponse(BaseModel):
    plan_id: int
    status: str
    issues: list[Issue] = Field(default_factory=list)
    recovery_options: list[RecoveryOption] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    health: PlanHealth

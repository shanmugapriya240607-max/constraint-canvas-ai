from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.planning import Priority, Name, ResourceType, PositiveInt
from app.schemas.solver import ScheduledTask
from app.schemas.analysis import Issue, PlanHealth

class BaseChange(BaseModel):
    type: str

class ResourceUnavailableChange(BaseChange):
    type: Literal["resource_unavailable"]
    resource_id: int

class ResourceCapacityChange(BaseChange):
    type: Literal["resource_capacity_change"]
    resource_id: int
    capacity: PositiveInt

class DeadlineChange(BaseChange):
    type: Literal["deadline_change"]
    task_id: int
    deadline: datetime

class PriorityChange(BaseChange):
    type: Literal["priority_change"]
    task_id: int
    priority: Priority

class TaskDurationChange(BaseChange):
    type: Literal["task_duration_change"]
    task_id: int
    duration_minutes: PositiveInt

class ResourceAvailabilityChange(BaseChange):
    type: Literal["resource_availability_change"]
    resource_id: int
    available_from: datetime
    available_until: datetime

class AddTemporaryResourceChange(BaseChange):
    type: Literal["add_temporary_resource"]
    name: Name
    resource_type: ResourceType
    capacity: PositiveInt

WhatIfChange = Annotated[
    Union[
        ResourceUnavailableChange,
        ResourceCapacityChange,
        DeadlineChange,
        PriorityChange,
        TaskDurationChange,
        ResourceAvailabilityChange,
        AddTemporaryResourceChange
    ],
    Field(discriminator="type")
]

class WhatIfRequest(BaseModel):
    changes: list[WhatIfChange]

class ScenarioRequest(BaseModel):
    name: str
    changes: list[WhatIfChange]

class CompareScenariosRequest(BaseModel):
    scenarios: list[ScenarioRequest]

class ScenarioMetrics(BaseModel):
    status: str
    makespan_minutes: int | None
    deadline_violations: int
    health_score: int

class WhatIfImpact(BaseModel):
    makespan_change_minutes: int | None
    health_change: int
    new_issues: list[Issue]
    resolved_issues: list[Issue]

class WhatIfResponse(BaseModel):
    plan_id: int
    baseline: ScenarioMetrics
    scenario: ScenarioMetrics
    changes: list[WhatIfChange]
    impact: WhatIfImpact
    schedule: list[ScheduledTask] = []

class ComparedScenarioMetrics(ScenarioMetrics):
    name: str
    issues_count: int

class ScenarioComparisonResponse(BaseModel):
    baseline: ScenarioMetrics
    scenarios: list[ComparedScenarioMetrics]

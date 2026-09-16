"""Static Pydantic v2 contracts for planning data; PATCH validates merged state."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import (
    AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, JsonValue,
    StringConstraints, model_validator,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ResourceType = Annotated[Name, AfterValidator(str.casefold)]
Description = Annotated[str, Field(max_length=10000)]
Timestamp = Annotated[AwareDatetime, AfterValidator(lambda value: value.astimezone(timezone.utc))]
PositiveInt = Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4, allow_inf_nan=False)]
Weight = Annotated[float, Field(gt=0, allow_inf_nan=False)]
DurationValue = Annotated[Decimal, Field(gt=0, le=2**31 - 1, max_digits=20, decimal_places=9, allow_inf_nan=False)]
DurationUnit = Literal["seconds", "minutes", "hours"]
PlanStatus = Literal["draft", "ready", "solved", "infeasible", "archived"]
Priority = Literal["low", "medium", "high", "critical"]
Hardness = Literal["hard", "soft"]
Source = Literal["manual", "ai", "memory", "system"]
ConstraintType = Literal[
    "deadline", "dependency", "resource_capacity", "availability",
    "max_work_hours", "preferred_resource", "preferred_time", "custom",
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatchModel(InputModel):
    non_nullable: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in sorted(self.non_nullable & self.model_fields_set):
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PlanCreate(InputModel):
    name: Name
    description: Description | None = None
    planning_start: Timestamp
    planning_end: Timestamp

    @model_validator(mode="after")
    def valid_window(self):
        if self.planning_end <= self.planning_start:
            raise ValueError("planning_end must be later than planning_start")
        return self


class PlanUpdate(PatchModel):
    non_nullable = {"name", "planning_start", "planning_end", "status"}
    name: Name | None = None
    description: Description | None = None
    planning_start: Timestamp | None = None
    planning_end: Timestamp | None = None
    status: PlanStatus | None = None


class PlanResponse(ResponseModel):
    id: int
    name: str
    description: str | None
    planning_start: datetime
    planning_end: datetime
    status: PlanStatus
    created_at: datetime
    updated_at: datetime


class ResourceCreate(InputModel):
    name: Name
    resource_type: ResourceType
    capacity: PositiveInt
    cost_per_hour: Money | None = None
    active: bool = True


class ResourceUpdate(PatchModel):
    non_nullable = {"name", "resource_type", "capacity", "active"}
    name: Name | None = None
    resource_type: ResourceType | None = None
    capacity: PositiveInt | None = None
    cost_per_hour: Money | None = None
    active: bool | None = None


class ResourceResponse(ResponseModel):
    id: int
    plan_id: int
    name: str
    resource_type: str
    capacity: int
    cost_per_hour: Decimal | None
    active: bool
    created_at: datetime
    updated_at: datetime


class AvailabilityCreate(InputModel):
    available_from: Timestamp
    available_until: Timestamp

    @model_validator(mode="after")
    def valid_window(self):
        if self.available_until <= self.available_from:
            raise ValueError("available_until must be later than available_from")
        return self


class AvailabilityUpdate(PatchModel):
    non_nullable = {"available_from", "available_until"}
    available_from: Timestamp | None = None
    available_until: Timestamp | None = None


class AvailabilityResponse(ResponseModel):
    id: int
    resource_id: int
    available_from: datetime
    available_until: datetime


def normalize_duration(minutes, value, unit) -> int:
    if minutes is not None:
        if value is not None or unit is not None:
            raise ValueError("Use duration_minutes OR duration_value with duration_unit")
        return minutes
    if value is None or unit is None:
        raise ValueError("Supply duration_minutes or both duration_value and duration_unit")
    # Exact rational arithmetic avoids Decimal context rounding at minute boundaries.
    numerator, denominator = value.as_integer_ratio()
    if unit == "seconds":
        denominator *= 60
    elif unit == "hours":
        numerator *= 60
    result = (numerator + denominator - 1) // denominator
    if not 0 < result <= 2**31 - 1:
        raise ValueError("Normalized duration is outside the supported integer minute range")
    return result


class TaskCreate(InputModel):
    name: Name
    description: Description | None = None
    duration_minutes: PositiveInt | None = None
    duration_value: DurationValue | None = None
    duration_unit: DurationUnit | None = None
    priority: Priority = "medium"
    earliest_start: Timestamp | None = None
    deadline: Timestamp | None = None

    @model_validator(mode="after")
    def validate_task(self):
        normalize_duration(self.duration_minutes, self.duration_value, self.duration_unit)
        if self.earliest_start is not None and self.deadline is not None:
            if self.deadline <= self.earliest_start:
                raise ValueError("deadline must be later than earliest_start")
        return self

    def persistence_values(self) -> dict:
        values = self.model_dump(exclude={"duration_value", "duration_unit"})
        values["duration_minutes"] = normalize_duration(self.duration_minutes, self.duration_value, self.duration_unit)
        return values


class TaskUpdate(PatchModel):
    non_nullable = {"name", "priority", "duration_minutes", "duration_value", "duration_unit"}
    name: Name | None = None
    description: Description | None = None
    duration_minutes: PositiveInt | None = None
    duration_value: DurationValue | None = None
    duration_unit: DurationUnit | None = None
    priority: Priority | None = None
    earliest_start: Timestamp | None = None
    deadline: Timestamp | None = None

    @model_validator(mode="after")
    def valid_duration_patch(self):
        if self.model_fields_set & {"duration_minutes", "duration_value", "duration_unit"}:
            normalize_duration(self.duration_minutes, self.duration_value, self.duration_unit)
        return self


class TaskResponse(ResponseModel):
    id: int
    plan_id: int
    name: str
    description: str | None
    duration_minutes: int
    priority: Priority
    earliest_start: datetime | None
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskRequirementCreate(InputModel):
    resource_type: ResourceType
    quantity: PositiveInt
    required_resource_id: PositiveInt | None = None


class TaskRequirementResponse(ResponseModel):
    id: int
    task_id: int
    resource_type: str
    quantity: int
    required_resource_id: int | None


class DependencyCreate(InputModel):
    before_task_id: PositiveInt
    after_task_id: PositiveInt


class DependencyResponse(ResponseModel):
    id: int
    plan_id: int
    before_task_id: int
    after_task_id: int


def validate_parameters(value: dict) -> dict:
    # Ordinary JSON only. Strings that resemble code remain inert data, never evaluated.
    try:
        encoded = json.dumps(value, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("parameters must contain finite, JSON-serializable data") from exc
    if len(encoded.encode("utf-8")) > 65536:
        raise ValueError("parameters must not exceed 64 KiB of JSON")
    return value


Parameters = Annotated[dict[str, JsonValue], AfterValidator(validate_parameters)]


class ConstraintRuleCreate(InputModel):
    constraint_type: ConstraintType
    hardness: Hardness = "hard"
    weight: Weight | None = None
    parameters: Parameters = Field(default_factory=dict)
    source: Source = "manual"
    enabled: bool = True

    @model_validator(mode="after")
    def soft_weight(self):
        if self.hardness == "soft" and self.weight is None:
            if "weight" in self.model_fields_set:
                raise ValueError("Soft constraints require a positive weight; omit it for default 1")
            self.weight = 1.0
        return self


class ConstraintRuleUpdate(PatchModel):
    non_nullable = {"constraint_type", "hardness", "parameters", "source", "enabled"}
    constraint_type: ConstraintType | None = None
    hardness: Hardness | None = None
    weight: Weight | None = None
    parameters: Parameters | None = None
    source: Source | None = None
    enabled: bool | None = None


class ConstraintRuleResponse(ResponseModel):
    id: int
    plan_id: int
    constraint_type: ConstraintType
    hardness: Hardness
    weight: float | None
    parameters: dict[str, JsonValue]
    source: Source
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ResourceFull(ResourceResponse):
    availability: list[AvailabilityResponse]


class TaskFull(TaskResponse):
    requirements: list[TaskRequirementResponse]


class FullPlanResponse(BaseModel):
    plan: PlanResponse
    resources: list[ResourceFull]
    tasks: list[TaskFull]
    dependencies: list[DependencyResponse]
    constraints: list[ConstraintRuleResponse]

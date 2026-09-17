"""Untrusted extraction contracts. Missing facts remain null, never domain defaults."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from app.schemas.planning import (
    AvailabilityCreate, Description, DurationUnit, DurationValue, Name, Parameters,
    PositiveInt, Priority, ResourceType, Timestamp,
)
from app.schemas.memory import ContextRouterResponse

ClientID = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,49}$")]
FieldPath = Annotated[str, Field(min_length=1, max_length=200)]
Operator = Literal["=", "!=", "<", "<=", ">", ">=", "before", "after", "depends_on"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class PlanDraft(StrictModel):
    name: Name | None = None
    description: Description | None = None
    planning_start: Timestamp | None = None
    planning_end: Timestamp | None = None


class ResourceDraft(StrictModel):
    client_id: ClientID
    name: Name | None = None
    resource_type: ResourceType | None = None
    capacity: PositiveInt | None = None
    availability: list[AvailabilityCreate] = Field(default_factory=list, max_length=100)


class TaskDraft(StrictModel):
    client_id: ClientID
    name: Name | None = None
    duration_value: DurationValue | None = None
    duration_unit: DurationUnit | None = None
    priority: Priority | None = None
    earliest_start: Timestamp | None = None
    deadline: Timestamp | None = None
    # Preserve unanchored times such as "5 PM"; no date/timezone is guessed.
    deadline_text: str | None = Field(default=None, max_length=500)


class RequirementDraft(StrictModel):
    task_id: ClientID
    resource_type: ResourceType | None = None
    quantity: PositiveInt | None = None
    required_resource_id: ClientID | None = None


class DependencyDraft(StrictModel):
    before_task_id: ClientID
    after_task_id: ClientID


class ConstraintDraft(StrictModel):
    semantic: Name
    operator: Operator
    hardness: Literal["hard", "soft"] = "hard"
    weight: float | None = Field(default=None, gt=0, le=1000, allow_inf_nan=False)
    # Reference parameters use client IDs, never database IDs.
    parameters: Parameters = Field(default_factory=dict)


class CustomField(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    type: Literal["string", "integer", "float", "boolean", "datetime", "time"]
    required: bool = Field(default=True, strict=True)
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def safe_definition(self):
        if self.name.startswith("model_") or hasattr(BaseModel, self.name):
            raise ValueError("Reserved field name")
        if self.minimum is not None or self.maximum is not None:
            if self.type not in ("integer", "float"):
                raise ValueError("Bounds only apply to numeric fields")
            if self.type == "integer" and any(
                bound is not None and not bound.is_integer() for bound in (self.minimum, self.maximum)
            ):
                raise ValueError("Integer field bounds must be whole numbers")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        return self


class InformationIssue(StrictModel):
    field: FieldPath
    reason: str = Field(min_length=1, max_length=500)


class Evidence(StrictModel):
    field: FieldPath
    quote: str = Field(min_length=1, max_length=2000)


class PlanningDraft(StrictModel):
    plan: PlanDraft
    resources: list[ResourceDraft] = Field(default_factory=list, max_length=30)
    tasks: list[TaskDraft] = Field(default_factory=list, max_length=50)
    requirements: list[RequirementDraft] = Field(default_factory=list, max_length=200)
    dependencies: list[DependencyDraft] = Field(default_factory=list, max_length=200)
    constraints: list[ConstraintDraft] = Field(default_factory=list, max_length=100)
    custom_fields: list[CustomField] = Field(default_factory=list, max_length=30)
    custom_values: Parameters = Field(default_factory=dict)
    missing_information: list[InformationIssue] = Field(default_factory=list, max_length=2000)
    ambiguities: list[InformationIssue] = Field(default_factory=list, max_length=200)
    evidence: list[Evidence] = Field(default_factory=list, max_length=1000)


class ParsePlanRequest(StrictModel):
    text: str = Field(min_length=1, max_length=20000, strict=True)
    existing_plan_id: PositiveInt | None = None
    include_context: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def validate_context(self):
        if not self.text.strip():
            raise ValueError("text must not be blank")
        if self.include_context and self.existing_plan_id is None:
            raise ValueError("include_context requires existing_plan_id")
        return self


class ClarificationQuestion(StrictModel):
    id: str
    field: str
    question: str
    reason: str
    allowed_answers: list[str] = Field(default_factory=list)


class ConstraintPreview(StrictModel):
    index: int
    semantic: str
    solver_supported: bool
    reason: str


class ParsePlanResponse(StrictModel):
    status: Literal["ready", "needs_clarification", "invalid"]
    draft: PlanningDraft | None = None
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    constraint_support: list[ConstraintPreview] = Field(default_factory=list)
    custom_values: dict[str, JsonValue] = Field(default_factory=dict)
    custom_fields_solver_supported: Literal[False] = False
    requires_confirmation: Literal[True] = True
    suggested_context: ContextRouterResponse | None = None


class ClarificationAnswer(StrictModel):
    field: FieldPath
    value: JsonValue


class ConfirmPlanRequest(StrictModel):
    confirmed: Literal[True]
    draft: PlanningDraft
    answers: list[ClarificationAnswer] = Field(default_factory=list, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if isinstance(value, dict) and value.get("confirmed") is not True:
            raise ValueError("confirmed must be the JSON boolean true")
        return value


class ConfirmPlanResponse(StrictModel):
    status: Literal["created"] = "created"
    plan_id: int
    created_counts: dict[str, int]

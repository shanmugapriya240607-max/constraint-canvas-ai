import re
from typing import List, Optional, Literal, Union, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

TIME_24H_REGEX = re.compile(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$")


class PlanningRequest(BaseModel):
    text: str = Field(..., description="Natural language planning requirement")


class Objective(BaseModel):
    type: Literal["MINIMIZE_MAKESPAN", "EARLIEST_FINISH", "LATEST_START"] = Field(
        ..., description="Optimization objective type"
    )
    description: Optional[str] = Field(None, description="Human readable objective description")


class Task(BaseModel):
    id: str = Field(..., description="Unique task identifier, e.g., task_1")
    name: str = Field(..., description="Task title or summary name")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes or null if unknown")
    earliest_start: Optional[str] = Field(None, description="Earliest start time in HH:MM 24-hour format or null")
    deadline: Optional[str] = Field(None, description="Latest completion deadline in HH:MM 24-hour format or null")
    depends_on: List[str] = Field(default_factory=list, description="List of task IDs that must precede this task")
    resources: List[str] = Field(default_factory=list, description="Required resources, e.g. ['person']")
    is_passive: bool = Field(False, description="True if task occurs in background without blocking active resources")
    source_text: Optional[str] = Field(None, description="Original source snippet describing the task")

    # Schedule & Priority fields computed in Phase 3
    start: Optional[str] = Field(None, description="Scheduled start time in HH:MM format")
    end: Optional[str] = Field(None, description="Scheduled end time in HH:MM format")
    execution_level: Optional[int] = Field(None, description="Topological execution order level")
    priority_score: Optional[int] = Field(None, description="Calculated priority score (0 to 100)")
    priority_reason: Optional[str] = Field(None, description="Explanation of why this task received its priority")
    is_critical: Optional[bool] = Field(None, description="True if task is on the critical path")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Task ID cannot be empty.")
        return v.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Task name cannot be empty.")
        return v.strip()

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Task duration_minutes must be a positive integer.")
        return v

    @field_validator("earliest_start", "deadline")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "":
            if not TIME_24H_REGEX.match(v.strip()):
                raise ValueError("Time must be in 24-hour HH:MM format (00:00 to 23:59).")
            return v.strip()
        return None


class ExtractedProblem(BaseModel):
    problem_title: str = Field(..., description="Brief title for the planning problem")
    objective: Optional[Objective] = Field(None, description="Extracted optimization objective")
    tasks: List[Task] = Field(default_factory=list, description="List of extracted tasks")
    missing_information: List[str] = Field(default_factory=list, description="Clarification questions for missing required data")
    ambiguities: List[str] = Field(default_factory=list, description="Ambiguous phrases or constraints noted")
    assumptions: List[str] = Field(default_factory=list, description="Default assumptions made during extraction")
    extraction_confidence: float = Field(..., description="Extraction confidence score between 0.0 and 1.0")
    parser_mode: Optional[str] = Field("OPENAI", description="Parser engine mode: OPENAI or OFFLINE_RULES")

    @field_validator("extraction_confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("extraction_confidence must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_unique_task_ids(self):
        seen_ids = set()
        for task in self.tasks:
            if task.id in seen_ids:
                raise ValueError(f"Duplicate task ID detected: '{task.id}'")
            seen_ids.add(task.id)
        return self


class ValidationErrorDetail(BaseModel):
    code: str
    message: str
    task_ids: List[str] = Field(default_factory=list)
    suggestion: Optional[str] = None


class ValidationResult(BaseModel):
    valid: bool
    errors: List[ValidationErrorDetail] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SolveResponse(BaseModel):
    status: str = Field(..., description="Result status: OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, NEEDS_INPUT, INVALID, ERROR")
    problem_title: Optional[str] = None
    objective: Optional[Union[Objective, str, Dict[str, Any]]] = None
    extraction_confidence: Optional[float] = None
    makespan_minutes: Optional[int] = None
    tasks: List[Task] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    questions: Optional[List[str]] = None
    explanation: Optional[str] = None
    errors: Optional[List[ValidationErrorDetail]] = None
    detail: Optional[str] = None
    history_saved: Optional[bool] = None
    warnings: Optional[List[str]] = None
    parser_mode: Optional[str] = Field("OPENAI", description="Parser engine mode: OPENAI or OFFLINE_RULES")



# Phase 4 History Schemas

class SolveRunHistoryItem(BaseModel):
    id: int
    problem_title: Optional[str] = None
    objective: Optional[Union[str, Dict[str, Any]]] = None
    status: str
    created_at: str
    task_count: int


class HistoryListResponse(BaseModel):
    count: int
    runs: List[SolveRunHistoryItem] = Field(default_factory=list)


class SolveRunDetailResponse(BaseModel):
    id: int
    original_text: str
    problem_title: Optional[str] = None
    objective: Optional[Union[str, Dict[str, Any]]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    status: str
    result: Optional[Dict[str, Any]] = None
    errors: Optional[Union[List[Any], Dict[str, Any]]] = None
    created_at: str

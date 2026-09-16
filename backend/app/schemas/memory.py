from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

class MemoryConsentUpdate(BaseModel):
    enabled: bool

class MemoryConsentResponse(BaseModel):
    memory_enabled: bool

class PlanningMemoryBase(BaseModel):
    memory_type: str = Field(..., max_length=50)
    key: str = Field(..., max_length=255)
    value: Dict[str, Any]
    source: str = Field(default="explicit", max_length=50)
    confidence: Optional[float] = None

class PlanningMemoryCreate(PlanningMemoryBase):
    pass

class PlanningMemoryUpdate(BaseModel):
    value: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None

class PlanningMemoryResponse(PlanningMemoryBase):
    id: int
    user_id: int
    confirmed: bool
    active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class HabitCandidateBase(BaseModel):
    habit_type: str = Field(..., max_length=50)
    normalized_pattern: str = Field(..., max_length=255)
    occurrence_count: int
    suggested_memory: Dict[str, Any]

class HabitCandidateResponse(HabitCandidateBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ContextRelevantMemory(BaseModel):
    memory_id: int
    type: str
    reason: str
    suggested_use: Dict[str, Any]


class ContextRouterResponse(BaseModel):
    plan_id: int
    memory_enabled: bool
    relevant_context: List[ContextRelevantMemory]
    requires_confirmation: bool = True


class ContextApplyRequest(BaseModel):
    memory_ids: List[int]

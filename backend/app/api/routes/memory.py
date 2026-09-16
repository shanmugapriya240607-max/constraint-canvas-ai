from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import User
from app.dependencies.auth import get_current_user
from app.schemas.memory import (
    MemoryConsentUpdate, MemoryConsentResponse,
    PlanningMemoryCreate, PlanningMemoryUpdate, PlanningMemoryResponse,
    HabitCandidateResponse
)
from app.services import memory_engine

router = APIRouter(prefix="/api/memory", tags=["Memory"])

@router.get("/consent", response_model=MemoryConsentResponse)
def get_consent_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    status = memory_engine.get_consent(db, current_user)
    return MemoryConsentResponse(memory_enabled=status)

@router.put("/consent", response_model=MemoryConsentResponse)
def update_consent_status(consent: MemoryConsentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    status = memory_engine.update_consent(db, current_user, consent)
    return MemoryConsentResponse(memory_enabled=status)

@router.post("", response_model=PlanningMemoryResponse)
def create_memory(data: PlanningMemoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return memory_engine.create_memory(db, current_user, data)

@router.get("", response_model=List[PlanningMemoryResponse])
def get_memories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return memory_engine.get_memories(db, current_user)

@router.get("/{memory_id}", response_model=PlanningMemoryResponse)
def get_memory(memory_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return memory_engine.get_memory(db, current_user, memory_id)

@router.patch("/{memory_id}", response_model=PlanningMemoryResponse)
def update_memory(memory_id: int, data: PlanningMemoryUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return memory_engine.update_memory(db, current_user, memory_id, data)

@router.delete("/{memory_id}")
def delete_memory(memory_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    memory_engine.delete_memory(db, current_user, memory_id)
    return {"detail": "Memory deleted"}

@router.delete("")
def delete_all_memories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    memory_engine.clear_all_memories(db, current_user)
    return {"detail": "All memories deleted"}

@router.get("/habits", response_model=List[HabitCandidateResponse])
def get_habits(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import select
    from app.models.memory import HabitCandidate
    return db.scalars(select(HabitCandidate).where(HabitCandidate.user_id == current_user.id)).all()

@router.post("/habits/detect", response_model=List[HabitCandidateResponse])
def detect_habits(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return memory_engine.detect_habits(db, current_user)

@router.post("/habits/{habit_id}/accept", response_model=PlanningMemoryResponse)
def accept_habit(habit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return memory_engine.accept_habit(db, current_user, habit_id)

@router.post("/habits/{habit_id}/reject")
def reject_habit(habit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    memory_engine.reject_habit(db, current_user, habit_id)
    return {"detail": "Habit rejected"}

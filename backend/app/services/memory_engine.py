import json
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from fastapi import HTTPException
from app.models.db_models import User
from app.models.memory import PlanningMemory, HabitCandidate
from app.schemas.memory import (
    MemoryConsentUpdate, PlanningMemoryCreate, PlanningMemoryUpdate,
    ContextRouterResponse, ContextRelevantMemory, ContextApplyRequest, ContextApplyResponse
)
from app.models.planning import Plan, ConstraintRule, utcnow
from app.schemas.planning import FullPlanResponse
from app.services.planning import full_plan

def get_consent(db: Session, user: User) -> bool:
    # refresh user just in case
    db.refresh(user)
    return user.memory_enabled

def update_consent(db: Session, user: User, consent: MemoryConsentUpdate) -> bool:
    user.memory_enabled = consent.enabled
    db.commit()
    db.refresh(user)
    return user.memory_enabled

def require_memory_enabled(user: User):
    if not user.memory_enabled:
        raise HTTPException(status_code=409, detail="Memory features are disabled. Please enable memory consent first.")

def create_memory(db: Session, user: User, data: PlanningMemoryCreate) -> PlanningMemory:
    require_memory_enabled(user)
    mem = PlanningMemory(
        user_id=user.id,
        memory_type=data.memory_type,
        key=data.key,
        value_json=data.value,
        source=data.source,
        confidence=data.confidence,
        confirmed=True,
        active=True
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem

def get_memories(db: Session, user: User) -> List[PlanningMemory]:
    return db.scalars(select(PlanningMemory).where(PlanningMemory.user_id == user.id)).all()

def get_memory(db: Session, user: User, memory_id: int) -> PlanningMemory:
    mem = db.scalars(select(PlanningMemory).where(PlanningMemory.user_id == user.id, PlanningMemory.id == memory_id)).first()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    return mem

def update_memory(db: Session, user: User, memory_id: int, data: PlanningMemoryUpdate) -> PlanningMemory:
    mem = get_memory(db, user, memory_id)
    if data.value is not None:
        mem.value_json = data.value
    if data.active is not None:
        mem.active = data.active
    db.commit()
    db.refresh(mem)
    return mem

def delete_memory(db: Session, user: User, memory_id: int):
    mem = get_memory(db, user, memory_id)
    db.delete(mem)
    db.commit()

def clear_all_memories(db: Session, user: User):
    memories = get_memories(db, user)
    for m in memories:
        db.delete(m)
    candidates = db.scalars(select(HabitCandidate).where(HabitCandidate.user_id == user.id)).all()
    for c in candidates:
        db.delete(c)
    db.commit()

def detect_habits(db: Session, user: User) -> List[HabitCandidate]:
    require_memory_enabled(user)
    
    # We examine recent plans for habits.
    # Deterministic simple rule:
    # preferred_resource: if the same resource type is preferred for tasks.
    # Since we can't do arbitrary complex data analysis easily in SQL, we'll implement a simple python loop.
    plans = db.scalars(select(Plan).where(Plan.user_id == user.id)).all()
    
    # Map pattern -> count
    # A pattern is a string like "preferred_resource:Dev:coding"
    patterns = {}
    pattern_to_payload = {}
    
    for p in plans:
        snapshot = full_plan(db, p)
        # Look for resources assigned to tasks in some way? Actually, the prompt says:
        # "same resource repeatedly preferred for same task/category"
        # We don't have historical assignment perfectly stored unless we check solver runs or just explicit constraints.
        res_dict = {r.id: r.name for r in snapshot.resources}
        for task in snapshot.tasks:
            for req in task.requirements:
                if req.required_resource_id and req.required_resource_id in res_dict:
                    r_name = res_dict[req.required_resource_id]
                    pat = f"preferred_resource:T{task.name}:R{r_name}"
                    patterns[pat] = patterns.get(pat, 0) + 1
                    if pat not in pattern_to_payload:
                        pattern_to_payload[pat] = {
                            "habit_type": "preferred_resource",
                            "suggested_memory": {
                                "task_name": task.name,
                                "resource_name": r_name
                            }
                        }

    # Now create candidate habits for any pattern >= 3
    new_candidates = []
    for pat, count in patterns.items():
        if count >= 3:
            # Check if candidate already exists
            existing = db.scalars(select(HabitCandidate).where(
                HabitCandidate.user_id == user.id,
                HabitCandidate.normalized_pattern == pat
            )).first()
            if not existing:
                payload = pattern_to_payload[pat]
                cand = HabitCandidate(
                    user_id=user.id,
                    habit_type=payload["habit_type"],
                    normalized_pattern=pat,
                    occurrence_count=count,
                    suggested_memory=payload["suggested_memory"],
                    status="pending"
                )
                db.add(cand)
                new_candidates.append(cand)
            elif existing.status == "pending":
                existing.occurrence_count = count
                new_candidates.append(existing)
    db.commit()
    return db.scalars(select(HabitCandidate).where(HabitCandidate.user_id == user.id)).all()

def accept_habit(db: Session, user: User, habit_id: int) -> PlanningMemory:
    require_memory_enabled(user)
    cand = db.scalars(select(HabitCandidate).where(HabitCandidate.user_id == user.id, HabitCandidate.id == habit_id)).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Habit candidate not found")
    if cand.status != "pending":
        raise HTTPException(status_code=400, detail="Habit candidate already processed")
    
    cand.status = "accepted"
    mem = PlanningMemory(
        user_id=user.id,
        memory_type=cand.habit_type,
        key=cand.normalized_pattern,
        value_json=cand.suggested_memory,
        source="habit",
        confidence=1.0,
        confirmed=True,
        active=True
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem

def reject_habit(db: Session, user: User, habit_id: int):
    cand = db.scalars(select(HabitCandidate).where(HabitCandidate.user_id == user.id, HabitCandidate.id == habit_id)).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Habit candidate not found")
    if cand.status != "pending":
        raise HTTPException(status_code=400, detail="Habit candidate already processed")
    
    cand.status = "rejected"
    db.commit()

def route_context(db: Session, plan_id: int, user: User) -> ContextRouterResponse:
    if not user.memory_enabled:
        return ContextRouterResponse(plan_id=plan_id, memory_enabled=False, relevant_context=[], requires_confirmation=True)
        
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.user_id == user.id))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    snapshot = full_plan(db, plan)
    memories = db.scalars(select(PlanningMemory).where(PlanningMemory.user_id == user.id, PlanningMemory.active == True, PlanningMemory.confirmed == True)).all()
    
    relevant = []
    task_names = {t.name for t in snapshot.tasks}
    resource_ids = {r.id for r in snapshot.resources}
    
    for mem in memories:
        is_relevant = False
        reason = ""
        if mem.memory_type == "preferred_resource":
            t_name = mem.value_json.get("task_name")
            r_id = mem.value_json.get("resource_id")
            if (not t_name or t_name in task_names) and (not r_id or r_id in resource_ids):
                is_relevant = True
                reason = "This preference refers to a task or resource in the current plan."
        elif mem.memory_type == "working_hours":
            is_relevant = True
            reason = "General working hours apply to all plans."
        else:
            # Add general rule or anything specific
            is_relevant = True
            reason = "Matches current planning context."
            
        if is_relevant:
            relevant.append(ContextRelevantMemory(
                memory_id=mem.id,
                type=mem.memory_type,
                reason=reason,
                suggested_use=mem.value_json
            ))
            
    return ContextRouterResponse(
        plan_id=plan_id,
        memory_enabled=True,
        relevant_context=relevant,
        requires_confirmation=True
    )

def _context_preference(memory, snapshot):
    """Resolve an explicit preference within this plan, without interpreting prose."""
    if memory.memory_type != "preferred_resource":
        raise HTTPException(status_code=422, detail="Selected context has no supported planning rule. Only structured preferred_resource context can be applied.")
    value = memory.value_json

    def resolve(items, kind):
        entity_id, name = value.get(f"{kind}_id"), value.get(f"{kind}_name")
        matches = [item for item in items
                   if (entity_id is not None or name is not None)
                   and (entity_id is None or (type(entity_id) is int and item.id == entity_id))
                   and (name is None or (isinstance(name, str) and item.name.casefold() == name.casefold()))]
        if len(matches) != 1:
            raise HTTPException(status_code=422, detail=f"Selected context must identify one {kind} in this plan.")
        return matches[0].id

    return {"task_id": resolve(snapshot.tasks, "task"),
            "resource_id": resolve(snapshot.resources, "resource")}


def apply_context(db: Session, plan_id: int, user: User, request: ContextApplyRequest) -> ContextApplyResponse:
    # Serialize applies with other plan writes before checking for existing rules.
    locked = db.execute(update(Plan).where(Plan.id == plan_id, Plan.user_id == user.id)
                        .values(updated_at=Plan.updated_at))
    if locked.rowcount != 1:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.refresh(user)
    require_memory_enabled(user)
    plan = db.get(Plan, plan_id)
    db.refresh(plan)
    snapshot = full_plan(db, plan)
    selected = sorted(set(request.memory_ids))
    memories = db.scalars(select(PlanningMemory).where(
        PlanningMemory.user_id == user.id, PlanningMemory.id.in_(selected)
    ).order_by(PlanningMemory.id)).all()
    if len(memories) != len(selected):
        raise HTTPException(status_code=404, detail="Selected memory not found")
    if any(not memory.active or not memory.confirmed for memory in memories):
        raise HTTPException(status_code=409, detail="Selected context must be active and approved.")
    # Validate the entire selection before any insertion: failure applies nothing.
    parameters = [_context_preference(memory, snapshot) for memory in memories]
    rules = list(db.scalars(select(ConstraintRule).where(ConstraintRule.plan_id == plan_id)
                            .order_by(ConstraintRule.id)))
    created, reused = [], []
    for params in parameters:
        existing = next((rule for rule in rules if rule.enabled
                         and rule.constraint_type == "preferred_resource"
                         and rule.hardness == "soft" and rule.parameters == params), None)
        if existing is not None:
            if existing not in reused:
                reused.append(existing)
            continue
        rule = ConstraintRule(plan_id=plan_id, constraint_type="preferred_resource",
                              hardness="soft", weight=1.0, parameters=params,
                              source="memory", enabled=True)
        db.add(rule)
        rules.append(rule)
        created.append(rule)
    if created:
        plan.updated_at = utcnow()
    db.commit()
    return ContextApplyResponse(
        **full_plan(db, plan).model_dump(), status="updated" if created else "unchanged",
        applied_memory_ids=selected, created_constraint_ids=[rule.id for rule in created],
        reused_constraint_ids=[rule.id for rule in reused if rule not in created],
    )

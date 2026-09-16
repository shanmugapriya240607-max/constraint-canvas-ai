"""Persistence and relationship validation only; no scheduling or allocation."""
from collections import defaultdict

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ConstraintRule, Plan, Resource, ResourceAvailability, Task, TaskDependency, TaskRequirement,
)
from app.schemas.planning import (
    AvailabilityResponse, ConstraintRuleResponse, DependencyResponse, FullPlanResponse,
    PlanResponse, ResourceFull, ResourceResponse, TaskFull, TaskRequirementResponse, TaskResponse,
)


def persist(db: Session, entity, conflict: str = "Planning data conflicts with an existing record"):
    db.add(entity)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict) from None
    db.refresh(entity)
    return entity


def delete_record(db: Session, entity) -> None:
    db.delete(entity)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This record is still referenced") from None


def validate_state(schema, values):
    try:
        return schema.model_validate(values)
    except ValidationError as exc:
        errors = [
            {"loc": ["body", *error["loc"]], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors) from None


def merge_state(schema, entity, patch: dict):
    values = {key: getattr(entity, key) for key in schema.model_fields}
    values.update(patch)
    return validate_state(schema, values)


def apply_values(entity, values: dict) -> None:
    for key, value in values.items():
        setattr(entity, key, value)


def ensure_acyclic(db: Session, plan_id: int, before: int, after: int) -> None:
    if before == after:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")
    edges = db.execute(
        select(TaskDependency.before_task_id, TaskDependency.after_task_id)
        .where(TaskDependency.plan_id == plan_id).order_by(TaskDependency.id)
    ).all()
    if (before, after) in edges:
        raise HTTPException(status_code=409, detail="Dependency already exists")
    adjacency = defaultdict(list)
    for predecessor, successor in edges:
        adjacency[predecessor].append(successor)
    # Adding before -> after creates a cycle iff after already reaches before.
    stack, visited = [after], set()
    while stack:
        current = stack.pop()
        if current == before:
            raise HTTPException(status_code=400, detail="Dependency would create a cycle")
        if current not in visited:
            visited.add(current)
            stack.extend(reversed(sorted(adjacency[current])))


def full_plan(db: Session, plan: Plan) -> FullPlanResponse:
    resources = db.scalars(select(Resource).where(Resource.plan_id == plan.id).order_by(Resource.id)).all()
    tasks = db.scalars(select(Task).where(Task.plan_id == plan.id).order_by(Task.id)).all()
    windows = db.scalars(
        select(ResourceAvailability).join(Resource)
        .where(Resource.plan_id == plan.id).order_by(ResourceAvailability.available_from, ResourceAvailability.id)
    ).all()
    requirements = db.scalars(
        select(TaskRequirement).where(TaskRequirement.plan_id == plan.id).order_by(TaskRequirement.id)
    ).all()
    availability_by_resource, requirements_by_task = defaultdict(list), defaultdict(list)
    for window in windows:
        availability_by_resource[window.resource_id].append(AvailabilityResponse.model_validate(window))
    for requirement in requirements:
        requirements_by_task[requirement.task_id].append(TaskRequirementResponse.model_validate(requirement))
    return FullPlanResponse(
        plan=PlanResponse.model_validate(plan),
        resources=[ResourceFull(
            **ResourceResponse.model_validate(resource).model_dump(),
            availability=availability_by_resource[resource.id],
        ) for resource in resources],
        tasks=[TaskFull(
            **TaskResponse.model_validate(task).model_dump(), requirements=requirements_by_task[task.id],
        ) for task in tasks],
        dependencies=[DependencyResponse.model_validate(edge) for edge in db.scalars(
            select(TaskDependency).where(TaskDependency.plan_id == plan.id).order_by(TaskDependency.id)
        )],
        constraints=[ConstraintRuleResponse.model_validate(rule) for rule in db.scalars(
            select(ConstraintRule).where(ConstraintRule.plan_id == plan.id).order_by(ConstraintRule.id)
        )],
    )

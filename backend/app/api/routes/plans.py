"""Authenticated planning CRUD. Rules are stored, never executed or solved."""
from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.dependencies.ownership import (
    CurrentUser, Database, OwnedPlan, PathID, WritablePlan, get_nested,
)
from app.models import (
    ConstraintRule, Plan, Resource, ResourceAvailability, Task, TaskDependency, TaskRequirement,
)
from app.schemas.planning import (
    AvailabilityCreate, AvailabilityResponse, AvailabilityUpdate,
    ConstraintRuleCreate, ConstraintRuleResponse, ConstraintRuleUpdate,
    DependencyCreate, DependencyResponse, FullPlanResponse,
    PlanCreate, PlanResponse, PlanUpdate,
    ResourceCreate, ResourceResponse, ResourceUpdate,
    TaskCreate, TaskRequirementCreate, TaskRequirementResponse, TaskResponse, TaskUpdate,
)
from app.services.planning import (
    apply_values, delete_record, ensure_acyclic, full_plan, merge_state, persist, validate_state,
)
from app.schemas.analysis import PlanAnalysisResponse
from app.services.analysis_engine import analyze_plan

router = APIRouter(prefix="/api/plans", tags=["planning data"])


@router.post("", response_model=PlanResponse, status_code=201)
def create_plan(payload: PlanCreate, db: Database, user: CurrentUser):
    return persist(db, Plan(user_id=user.id, **payload.model_dump()))


@router.get("", response_model=list[PlanResponse])
def list_plans(db: Database, user: CurrentUser):
    return db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.id)).all()


@router.get("/{plan_id}", response_model=PlanResponse)
def read_plan(plan: OwnedPlan):
    return plan


@router.patch("/{plan_id}", response_model=PlanResponse)
def update_plan(payload: PlanUpdate, plan: WritablePlan, db: Database):
    changes = payload.model_dump(exclude_unset=True)
    status = changes.pop("status", plan.status)
    validated = merge_state(PlanCreate, plan, changes)
    apply_values(plan, validated.model_dump())
    plan.status = status
    return persist(db, plan)


@router.delete("/{plan_id}", status_code=204)
def remove_plan(plan: WritablePlan, db: Database):
    delete_record(db, plan)
    return Response(status_code=204)


@router.get("/{plan_id}/full", response_model=FullPlanResponse)
def read_full_plan(plan: OwnedPlan, db: Database):
    return full_plan(db, plan)


@router.get("/{plan_id}/analysis", response_model=PlanAnalysisResponse)
def get_plan_analysis(plan: OwnedPlan, db: Database):
    return analyze_plan(db, plan)


@router.post("/{plan_id}/resources", response_model=ResourceResponse, status_code=201)
def create_resource(payload: ResourceCreate, plan: WritablePlan, db: Database):
    return persist(db, Resource(
        plan_id=plan.id, name_key=payload.name.casefold(), **payload.model_dump(),
    ), "A resource with this name already exists in the plan")


@router.get("/{plan_id}/resources", response_model=list[ResourceResponse])
def list_resources(plan: OwnedPlan, db: Database):
    return db.scalars(select(Resource).where(Resource.plan_id == plan.id).order_by(Resource.id)).all()


@router.get("/{plan_id}/resources/{resource_id}", response_model=ResourceResponse)
def read_resource(resource_id: PathID, plan: OwnedPlan, db: Database):
    return get_nested(db, Resource, resource_id, plan_id=plan.id)


@router.patch("/{plan_id}/resources/{resource_id}", response_model=ResourceResponse)
def update_resource(resource_id: PathID, payload: ResourceUpdate, plan: WritablePlan, db: Database):
    resource = get_nested(db, Resource, resource_id, plan_id=plan.id)
    state = merge_state(ResourceCreate, resource, payload.model_dump(exclude_unset=True))
    if state.resource_type != resource.resource_type and db.scalar(
        select(TaskRequirement.id).where(TaskRequirement.required_resource_id == resource.id).limit(1)
    ) is not None:
        raise HTTPException(status_code=409, detail="Remove specific resource requirements before changing resource_type")
    apply_values(resource, state.model_dump())
    resource.name_key = resource.name.casefold()
    return persist(db, resource, "A resource with this name already exists in the plan")


@router.delete("/{plan_id}/resources/{resource_id}", status_code=204)
def remove_resource(resource_id: PathID, plan: WritablePlan, db: Database):
    resource = get_nested(db, Resource, resource_id, plan_id=plan.id)
    if db.scalar(select(TaskRequirement.id).where(TaskRequirement.required_resource_id == resource.id).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Remove specific resource requirements before deleting this resource")
    delete_record(db, resource)
    return Response(status_code=204)


@router.post("/{plan_id}/resources/{resource_id}/availability", response_model=AvailabilityResponse, status_code=201)
def create_availability(resource_id: PathID, payload: AvailabilityCreate, plan: WritablePlan, db: Database):
    resource = get_nested(db, Resource, resource_id, plan_id=plan.id)
    return persist(db, ResourceAvailability(resource_id=resource.id, **payload.model_dump()))


@router.get("/{plan_id}/resources/{resource_id}/availability", response_model=list[AvailabilityResponse])
def list_availability(resource_id: PathID, plan: OwnedPlan, db: Database):
    resource = get_nested(db, Resource, resource_id, plan_id=plan.id)
    return db.scalars(select(ResourceAvailability).where(ResourceAvailability.resource_id == resource.id)
                      .order_by(ResourceAvailability.available_from, ResourceAvailability.id)).all()


@router.patch("/{plan_id}/resources/{resource_id}/availability/{availability_id}", response_model=AvailabilityResponse)
def update_availability(resource_id: PathID, availability_id: PathID, payload: AvailabilityUpdate, plan: WritablePlan, db: Database):
    resource = get_nested(db, Resource, resource_id, plan_id=plan.id)
    window = get_nested(db, ResourceAvailability, availability_id, resource_id=resource.id)
    state = merge_state(AvailabilityCreate, window, payload.model_dump(exclude_unset=True))
    apply_values(window, state.model_dump())
    return persist(db, window)


@router.delete("/{plan_id}/resources/{resource_id}/availability/{availability_id}", status_code=204)
def remove_availability(resource_id: PathID, availability_id: PathID, plan: WritablePlan, db: Database):
    resource = get_nested(db, Resource, resource_id, plan_id=plan.id)
    window = get_nested(db, ResourceAvailability, availability_id, resource_id=resource.id)
    delete_record(db, window)
    return Response(status_code=204)


@router.post("/{plan_id}/tasks", response_model=TaskResponse, status_code=201)
def create_task(payload: TaskCreate, plan: WritablePlan, db: Database):
    return persist(db, Task(plan_id=plan.id, **payload.persistence_values()))


@router.get("/{plan_id}/tasks", response_model=list[TaskResponse])
def list_tasks(plan: OwnedPlan, db: Database):
    return db.scalars(select(Task).where(Task.plan_id == plan.id).order_by(Task.id)).all()


@router.get("/{plan_id}/tasks/{task_id}", response_model=TaskResponse)
def read_task(task_id: PathID, plan: OwnedPlan, db: Database):
    return get_nested(db, Task, task_id, plan_id=plan.id)


@router.patch("/{plan_id}/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: PathID, payload: TaskUpdate, plan: WritablePlan, db: Database):
    task = get_nested(db, Task, task_id, plan_id=plan.id)
    changes = payload.model_dump(exclude_unset=True)
    values = {key: getattr(task, key) for key in TaskCreate.model_fields if key not in {"duration_value", "duration_unit"}}
    if "duration_value" in changes or "duration_unit" in changes:
        values.pop("duration_minutes")
    values.update(changes)
    state = validate_state(TaskCreate, values)
    apply_values(task, state.persistence_values())
    return persist(db, task)


@router.delete("/{plan_id}/tasks/{task_id}", status_code=204)
def remove_task(task_id: PathID, plan: WritablePlan, db: Database):
    task = get_nested(db, Task, task_id, plan_id=plan.id)
    delete_record(db, task)
    return Response(status_code=204)


@router.post("/{plan_id}/tasks/{task_id}/requirements", response_model=TaskRequirementResponse, status_code=201)
def create_requirement(task_id: PathID, payload: TaskRequirementCreate, plan: WritablePlan, db: Database):
    task = get_nested(db, Task, task_id, plan_id=plan.id)
    if payload.required_resource_id is not None:
        resource = get_nested(db, Resource, payload.required_resource_id, plan_id=plan.id)
        if resource.resource_type != payload.resource_type:
            raise HTTPException(status_code=400, detail="Requirement resource_type must match the specific resource")
    return persist(db, TaskRequirement(task_id=task.id, plan_id=plan.id, **payload.model_dump()))


@router.get("/{plan_id}/tasks/{task_id}/requirements", response_model=list[TaskRequirementResponse])
def list_requirements(task_id: PathID, plan: OwnedPlan, db: Database):
    task = get_nested(db, Task, task_id, plan_id=plan.id)
    return db.scalars(select(TaskRequirement).where(TaskRequirement.task_id == task.id).order_by(TaskRequirement.id)).all()


@router.delete("/{plan_id}/tasks/{task_id}/requirements/{requirement_id}", status_code=204)
def remove_requirement(task_id: PathID, requirement_id: PathID, plan: WritablePlan, db: Database):
    task = get_nested(db, Task, task_id, plan_id=plan.id)
    requirement = get_nested(db, TaskRequirement, requirement_id, task_id=task.id)
    delete_record(db, requirement)
    return Response(status_code=204)


@router.post("/{plan_id}/dependencies", response_model=DependencyResponse, status_code=201)
def create_dependency(payload: DependencyCreate, plan: WritablePlan, db: Database):
    get_nested(db, Task, payload.before_task_id, plan_id=plan.id)
    get_nested(db, Task, payload.after_task_id, plan_id=plan.id)
    ensure_acyclic(db, plan.id, payload.before_task_id, payload.after_task_id)
    return persist(db, TaskDependency(plan_id=plan.id, **payload.model_dump()), "Dependency already exists")


@router.get("/{plan_id}/dependencies", response_model=list[DependencyResponse])
def list_dependencies(plan: OwnedPlan, db: Database):
    return db.scalars(select(TaskDependency).where(TaskDependency.plan_id == plan.id).order_by(TaskDependency.id)).all()


@router.delete("/{plan_id}/dependencies/{dependency_id}", status_code=204)
def remove_dependency(dependency_id: PathID, plan: WritablePlan, db: Database):
    dependency = get_nested(db, TaskDependency, dependency_id, plan_id=plan.id)
    delete_record(db, dependency)
    return Response(status_code=204)


@router.post("/{plan_id}/constraints", response_model=ConstraintRuleResponse, status_code=201)
def create_constraint(payload: ConstraintRuleCreate, plan: WritablePlan, db: Database):
    return persist(db, ConstraintRule(plan_id=plan.id, **payload.model_dump()))


@router.get("/{plan_id}/constraints", response_model=list[ConstraintRuleResponse])
def list_constraints(plan: OwnedPlan, db: Database):
    return db.scalars(select(ConstraintRule).where(ConstraintRule.plan_id == plan.id).order_by(ConstraintRule.id)).all()


@router.patch("/{plan_id}/constraints/{constraint_id}", response_model=ConstraintRuleResponse)
def update_constraint(constraint_id: PathID, payload: ConstraintRuleUpdate, plan: WritablePlan, db: Database):
    rule = get_nested(db, ConstraintRule, constraint_id, plan_id=plan.id)
    changes = payload.model_dump(exclude_unset=True)
    values = {key: getattr(rule, key) for key in ConstraintRuleCreate.model_fields}
    values.update(changes)
    if values["hardness"] == "soft" and values["weight"] is None and "weight" not in changes:
        values.pop("weight")
    state = validate_state(ConstraintRuleCreate, values)
    apply_values(rule, state.model_dump())
    return persist(db, rule)


@router.delete("/{plan_id}/constraints/{constraint_id}", status_code=204)
def remove_constraint(constraint_id: PathID, plan: WritablePlan, db: Database):
    rule = get_nested(db, ConstraintRule, constraint_id, plan_id=plan.id)
    delete_record(db, rule)
    return Response(status_code=204)

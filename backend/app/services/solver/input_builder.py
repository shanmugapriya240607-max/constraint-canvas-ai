"""Validate a detached planning snapshot and normalize all solver time to integers."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import heapq

from pydantic import ValidationError
from app.schemas.planning import FullPlanResponse
from app.schemas.solver import (
    AvailabilityRule, CapacityRule, DeadlineRule, DependencyRule, MaxWorkRule,
    PreferredResourceRule, PreferredTimeRule,
)

MINUTE_US = 60_000_000
PRIORITY = {"low":1, "medium":2, "high":4, "critical":8}


class SolverInputError(ValueError):
    pass


def minute_offset(value: datetime, anchor: datetime, *, ceil: bool = False) -> int:
    delta = value - anchor
    microseconds = ((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds)
    return -(-microseconds // MINUTE_US) if ceil else microseconds // MINUTE_US


def normalized_type(value: str) -> str:
    return value.strip().casefold()


@dataclass
class SolverInput:
    snapshot: FullPlanResponse
    horizon: int
    earliest: dict[int, int]
    deadlines: dict[int, int]
    capacities: dict[int, int]
    windows: dict[int, list[tuple[int, int]]]
    dependencies: list[tuple[int, int]]
    candidates: dict[int, list[int]]
    max_work_minutes: dict[int, int] = field(default_factory=dict)
    # (rule type, parsed parameter schema, integer weight scaled by 1000)
    preferences: list[tuple[str, object, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_graph(task_ids: set[int], edges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    edges = sorted(set(edges))
    degrees, successors = dict.fromkeys(task_ids, 0), defaultdict(list)
    for before, after in edges:
        if before not in task_ids or after not in task_ids or before == after:
            raise SolverInputError("Dependencies must reference distinct tasks within the plan")
        degrees[after] += 1
        successors[before].append(after)
    ready = [task for task, degree in degrees.items() if degree == 0]
    heapq.heapify(ready)
    visited = 0
    while ready:
        current = heapq.heappop(ready)
        visited += 1
        for successor in successors[current]:
            degrees[successor] -= 1
            if degrees[successor] == 0:
                heapq.heappush(ready, successor)
    if visited != len(task_ids):
        raise SolverInputError("Dependencies contain a cycle")
    return edges


def build_input(snapshot: FullPlanResponse) -> SolverInput:
    plan = snapshot.plan
    horizon = minute_offset(plan.planning_end, plan.planning_start)
    if not 1 <= horizon <= 44640:
        raise SolverInputError("Planning horizon must contain 1 to 44640 whole minutes (31 days)")
    if not 1 <= len(snapshot.tasks) <= 50 or len(snapshot.resources) > 30:
        raise SolverInputError("Solve supports 1–50 tasks and at most 30 resources")
    if sum(len(task.requirements) for task in snapshot.tasks) > 200 or len(snapshot.constraints) > 100:
        raise SolverInputError("Solve supports at most 200 requirements and 100 constraint rules")
    tasks = {task.id:task for task in snapshot.tasks}
    resources = {resource.id:resource for resource in snapshot.resources}
    if len(tasks) != len(snapshot.tasks) or len(resources) != len(snapshot.resources):
        raise SolverInputError("Duplicate task or resource IDs")
    data = SolverInput(snapshot, horizon, {}, {}, {}, {}, [], {})
    for resource in snapshot.resources:
        if resource.plan_id != plan.id or not 1 <= resource.capacity <= 1000:
            raise SolverInputError("Resources must belong to this plan and have capacity 1–1000")
        data.capacities[resource.id] = resource.capacity
        if len(resource.availability) > 100:
            raise SolverInputError("At most 100 availability windows per resource are supported")
        windows = []
        for window in resource.availability:
            if window.resource_id != resource.id or window.available_until <= window.available_from:
                raise SolverInputError("Invalid resource availability record")
            start = max(0, minute_offset(window.available_from, plan.planning_start, ceil=True))
            end = min(horizon, minute_offset(window.available_until, plan.planning_start))
            if start < end:
                windows.append((start,end))
        # Presence of records with no usable intersection means unavailable, not unrestricted.
        data.windows[resource.id] = sorted(set(windows)) if resource.availability else [(0,horizon)]
    seen_requirements = set()
    for task in snapshot.tasks:
        if task.plan_id != plan.id or task.priority not in PRIORITY:
            raise SolverInputError("Task plan or priority is invalid")
        if not 1 <= task.duration_minutes <= horizon:
            raise SolverInputError(f"Task {task.id} duration must fit inside the whole planning horizon")
        lower = minute_offset(task.earliest_start, plan.planning_start, ceil=True) if task.earliest_start else 0
        upper = minute_offset(task.deadline, plan.planning_start) if task.deadline else horizon
        if upper < 0 or lower > horizon:
            raise SolverInputError(f"Task {task.id} deadline/earliest start is outside the planning horizon")
        if task.earliest_start and task.deadline and task.deadline <= task.earliest_start:
            raise SolverInputError(f"Task {task.id} has an invalid time window")
        data.earliest[task.id], data.deadlines[task.id] = max(0,lower), min(horizon,upper)
        for requirement in task.requirements:
            if requirement.id in seen_requirements or requirement.task_id != task.id or not 1 <= requirement.quantity <= 1000:
                raise SolverInputError("Invalid task resource requirement")
            seen_requirements.add(requirement.id)
            kind = normalized_type(requirement.resource_type)
            candidates = sorted(resource.id for resource in snapshot.resources
                                if resource.active and normalized_type(resource.resource_type) == kind)
            if requirement.required_resource_id is not None:
                specific = resources.get(requirement.required_resource_id)
                if specific is None or not specific.active or normalized_type(specific.resource_type) != kind:
                    raise SolverInputError("Specific resource must be active, matching, and in the same plan")
                candidates = [specific.id]
            if not candidates:
                raise SolverInputError(f"Requirement {requirement.id} has no active matching resource")
            data.candidates[requirement.id] = candidates
    edges = []
    for edge in snapshot.dependencies:
        if edge.plan_id != plan.id:
            raise SolverInputError("Dependency belongs to another plan")
        edges.append((edge.before_task_id,edge.after_task_id))

    hard_schemas = {"deadline":DeadlineRule,"dependency":DependencyRule,"resource_capacity":CapacityRule,
                    "availability":AvailabilityRule,"max_work_hours":MaxWorkRule}
    soft_schemas = {"preferred_resource":PreferredResourceRule,"preferred_time":PreferredTimeRule}
    for rule in sorted(snapshot.constraints, key=lambda item:item.id):
        if rule.plan_id != plan.id:
            raise SolverInputError("Constraint belongs to another plan")
        if not rule.enabled:
            continue
        schemas = hard_schemas if rule.hardness == "hard" else soft_schemas
        schema = schemas.get(rule.constraint_type)
        if schema is None:
            if rule.hardness == "hard":
                raise SolverInputError(f"Enabled hard constraint {rule.id} has unsupported type '{rule.constraint_type}'")
            data.warnings.append(f"Unsupported soft constraint {rule.id} ({rule.constraint_type}) was not applied")
            continue
        try:
            params = schema.model_validate(rule.parameters)
        except ValidationError as exc:
            raise SolverInputError(f"Constraint {rule.id} has invalid parameters for {rule.constraint_type}") from exc
        for name in ("task_id","before_task_id","after_task_id"):
            if hasattr(params,name) and getattr(params,name) not in tasks:
                raise SolverInputError(f"Constraint {rule.id} references a task outside this plan")
        if hasattr(params,"resource_id") and params.resource_id not in resources:
            raise SolverInputError(f"Constraint {rule.id} references a resource outside this plan")
        if rule.hardness == "soft":
            try:
                weight = Decimal(str(rule.weight))
            except InvalidOperation as exc:
                raise SolverInputError("Supported soft rules require a positive numeric weight") from exc
            if not weight.is_finite() or not 0 < weight <= 1000:
                raise SolverInputError("Supported soft rule weights must be positive and at most 1000")
            scaled = max(1,int((weight*1000).to_integral_value(rounding=ROUND_HALF_UP)))
            data.preferences.append((rule.constraint_type,params,scaled))
        elif isinstance(params,DeadlineRule):
            deadline = minute_offset(params.deadline,plan.planning_start)
            if deadline < 0:
                raise SolverInputError(f"Constraint {rule.id} deadline is before planning_start")
            data.deadlines[params.task_id] = min(data.deadlines[params.task_id],deadline)
        elif isinstance(params,DependencyRule):
            edges.append((params.before_task_id,params.after_task_id))
        elif isinstance(params,CapacityRule):
            data.capacities[params.resource_id] = min(data.capacities[params.resource_id],params.capacity)
        elif isinstance(params,AvailabilityRule):
            lower = minute_offset(params.available_from,plan.planning_start,ceil=True)
            upper = minute_offset(params.available_until,plan.planning_start)
            data.windows[params.resource_id] = sorted(set((max(start,lower),min(end,upper))
                for start,end in data.windows[params.resource_id] if max(start,lower) < min(end,upper)))
        elif isinstance(params,MaxWorkRule):
            maximum = int(params.max_hours * 60)
            data.max_work_minutes[params.resource_id] = min(data.max_work_minutes.get(params.resource_id,maximum),maximum)
    data.dependencies = validate_graph(set(tasks),edges)
    # Active but insufficient capacity is a well-formed, infeasible model. CP-SAT
    # will prove it through its allocation equalities; do not synthesize a schedule.
    return data

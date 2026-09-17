"""Validate previews and atomically assemble a confirmed planning-domain aggregate."""
import json
from collections import defaultdict, deque
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.models import Plan, Resource, ResourceAvailability, Task, TaskDependency, TaskRequirement, ConstraintRule
from app.schemas.ai_parser import InformationIssue, ParsePlanResponse, PlanningDraft, ConfirmPlanResponse
from app.schemas.planning import PlanCreate, ResourceCreate, TaskCreate, TaskRequirementCreate, ConstraintRuleCreate
from app.services.planning import ensure_acyclic
from app.services.ai.clarification import apply_answers, question_list, source_issues
from app.services.ai.constraint_mapping import map_constraint
from app.services.ai.dynamic_schema import validate_custom_fields

MAX_EXTRACTION_BYTES = 256_000


def _acyclic(task_ids, edges):
    successors, degree = defaultdict(list), dict.fromkeys(task_ids, 0)
    seen = set()
    for before, after in edges:
        if before not in degree or after not in degree or before == after or (before, after) in seen:
            raise ValueError("Invalid, duplicate, or unknown dependency reference")
        seen.add((before, after))
        degree[after] += 1
        successors[before].append(after)
    queue = deque(key for key, value in degree.items() if value == 0)
    count = 0
    while queue:
        current = queue.popleft()
        count += 1
        for successor in successors[current]:
            degree[successor] -= 1
            if not degree[successor]:
                queue.append(successor)
    if count != len(degree):
        raise ValueError("Dependencies contain a cycle")


def inspect_draft(draft: PlanningDraft, source_text: str | None = None) -> ParsePlanResponse:
    issues = list(draft.missing_information) + list(draft.ambiguities)
    errors, support = [], []
    custom_values = {}

    def missing(path):
        issues.append(InformationIssue(field=path, reason="Required planning information was not specified."))

    def validate(schema, data, location):
        try:
            schema.model_validate(data)
        except ValidationError:
            errors.append(f"{location} does not satisfy the planning-domain schema")

    for field in ("name", "planning_start", "planning_end"):
        if getattr(draft.plan, field) is None:
            missing("plan." + field)
    if all(getattr(draft.plan, key) is not None for key in ("name", "planning_start", "planning_end")):
        validate(PlanCreate, draft.plan.model_dump(), "plan")
    if not draft.tasks:
        missing("tasks")
    task_ids = {task.client_id: i + 1 for i, task in enumerate(draft.tasks)}
    resource_ids = {resource.client_id: i + 1 for i, resource in enumerate(draft.resources)}
    if len(task_ids) != len(draft.tasks) or len(resource_ids) != len(draft.resources):
        errors.append("Client IDs must be unique within each collection")
    if len({resource.name.casefold() for resource in draft.resources if resource.name}) != len([r for r in draft.resources if r.name]):
        errors.append("Resource names must be unique ignoring case")
    for index, resource in enumerate(draft.resources):
        for field in ("name", "resource_type", "capacity"):
            if getattr(resource, field) is None:
                missing(f"resources.{index}.{field}")
        if all(getattr(resource, key) is not None for key in ("name", "resource_type", "capacity")):
            validate(ResourceCreate, resource.model_dump(exclude={"client_id", "availability"}), f"resources.{index}")
    for index, task in enumerate(draft.tasks):
        for field in ("name", "duration_value", "duration_unit", "priority"):
            if getattr(task, field) is None:
                missing(f"tasks.{index}.{field}")
        if task.deadline_text and task.deadline is None:
            issues.append(InformationIssue(field=f"tasks.{index}.deadline",
                reason="A deadline was mentioned but needs an explicit date, time and timezone."))
        if all(getattr(task, key) is not None for key in ("name", "duration_value", "duration_unit", "priority")):
            validate(TaskCreate, task.model_dump(exclude={"client_id", "deadline_text"}), f"tasks.{index}")
    resources = {resource.client_id: resource for resource in draft.resources}
    for index, requirement in enumerate(draft.requirements):
        if requirement.task_id not in task_ids:
            errors.append(f"requirements.{index} references an unknown task")
        for field in ("resource_type", "quantity"):
            if getattr(requirement, field) is None:
                missing(f"requirements.{index}.{field}")
        if requirement.required_resource_id is not None:
            resource = resources.get(requirement.required_resource_id)
            if resource is None or (resource.resource_type is not None and requirement.resource_type is not None
                                    and resource.resource_type != requirement.resource_type):
                errors.append(f"requirements.{index} has an unknown or mismatched specific resource")
        if requirement.resource_type and not any(r.resource_type == requirement.resource_type for r in draft.resources):
            issues.append(InformationIssue(field="resources", reason="A task requires a resource type with no declared resource."))
    edges = [(edge.before_task_id, edge.after_task_id) for edge in draft.dependencies]
    for index, rule in enumerate(draft.constraints):
        try:
            preview, mapped = map_constraint(rule, index, task_ids, resource_ids)
            support.append(preview)
            if mapped.enabled and mapped.constraint_type == "dependency":
                # Check cycles spanning explicit edges and mapped rules.
                inverse = {value: key for key, value in task_ids.items()}
                edge = (inverse[mapped.parameters["before_task_id"]], inverse[mapped.parameters["after_task_id"]])
                if edge not in edges:
                    edges.append(edge)
        except (ValueError, TypeError):
            errors.append(f"constraints.{index} has invalid parameters or references")
    try:
        _acyclic(task_ids, edges)
    except ValueError as error:
        errors.append(str(error))
    try:
        custom_values = validate_custom_fields(draft.custom_fields, draft.custom_values)
    except ValidationError as error:
        for issue in error.errors():
            if issue["type"] == "missing":
                missing("custom_values." + str(issue["loc"][0]))
            else:
                errors.append("Custom field values do not satisfy their declared schema")
    except (ValueError, TypeError):
        errors.append("Custom field definitions are invalid")
    if source_text is not None:
        issues.extend(source_issues(draft, source_text))
    questions = question_list(issues)
    # Carry deterministic findings into the reviewed representation. Confirmation must resolve them.
    reviewed = draft.model_copy(deep=True)
    reviewed.missing_information = [InformationIssue(field=q.field, reason=q.reason) for q in questions]
    return ParsePlanResponse(
        status="invalid" if errors else "needs_clarification" if questions else "ready",
        draft=reviewed, questions=questions, errors=list(dict.fromkeys(errors)),
        constraint_support=support, custom_values=custom_values,
    )


def parse_plan(client, text):
    raw = client.extract(text)
    try:
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_EXTRACTION_BYTES:
            raise ValueError("Oversized extraction")
        # Reject duplicate JSON keys instead of silently trusting the last occurrence.
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON key")
                result[key] = value
            return result
        parsed = json.loads(raw, object_pairs_hook=unique_object)
        draft = PlanningDraft.model_validate(parsed)
    except (ValueError, TypeError, RecursionError):
        return ParsePlanResponse(status="invalid", errors=["Gemini output failed safe structured validation"])
    return inspect_draft(draft, source_text=text)


def confirm_plan(db, user, request):
    try:
        draft = apply_answers(request.draft, request.answers)
    except ValidationError:
        raise HTTPException(422, "Clarification answers do not satisfy the extraction schema") from None
    preview = inspect_draft(draft)
    if preview.status != "ready":
        raise HTTPException(422, detail={
            "status": preview.status,
            "questions": [question.model_dump() for question in preview.questions],
            "errors": preview.errors,
        })
    # Reuse canonical domain schemas and graph validation. Never call routes that commit
    # each child separately: a confirmed aggregate must commit or roll back as one unit.
    try:
        plan_data = PlanCreate.model_validate(draft.plan.model_dump())
        plan = Plan(user_id=user.id, **plan_data.model_dump())
        db.add(plan)
        db.flush()
        resources, tasks = {}, {}
        window_count = 0
        for resource in draft.resources:
            validated = ResourceCreate.model_validate(resource.model_dump(exclude={"client_id", "availability"}))
            entity = Resource(plan_id=plan.id, name_key=validated.name.casefold(), **validated.model_dump())
            db.add(entity)
            db.flush()
            resources[resource.client_id] = entity.id
            for window in resource.availability:
                db.add(ResourceAvailability(resource_id=entity.id, **window.model_dump()))
                window_count += 1
        for task in draft.tasks:
            validated = TaskCreate.model_validate(task.model_dump(exclude={"client_id", "deadline_text"}))
            entity = Task(plan_id=plan.id, **validated.persistence_values())
            db.add(entity)
            db.flush()
            tasks[task.client_id] = entity.id
        for requirement in draft.requirements:
            validated = TaskRequirementCreate(
                resource_type=requirement.resource_type, quantity=requirement.quantity,
                required_resource_id=resources.get(requirement.required_resource_id),
            )
            db.add(TaskRequirement(task_id=tasks[requirement.task_id], plan_id=plan.id, **validated.model_dump()))
        for edge in draft.dependencies:
            before, after = tasks[edge.before_task_id], tasks[edge.after_task_id]
            ensure_acyclic(db, plan.id, before, after)
            db.add(TaskDependency(plan_id=plan.id, before_task_id=before, after_task_id=after))
            db.flush()
        disabled_count = 0
        for index, rule in enumerate(draft.constraints):
            _, mapped = map_constraint(rule, index, tasks, resources)
            disabled_count += not mapped.enabled
            db.add(ConstraintRule(plan_id=plan.id, **mapped.model_dump(mode="json")))
        if draft.custom_fields:
            metadata = ConstraintRuleCreate(
                constraint_type="custom", source="ai", enabled=False,
                parameters={"definitions": [item.model_dump() for item in draft.custom_fields],
                            "values": preview.custom_values, "solver_supported": False},
            )
            db.add(ConstraintRule(plan_id=plan.id, **metadata.model_dump(mode="json")))
            disabled_count += 1
        db.flush()
        plan_id = plan.id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Confirmed planning data conflicts with an existing record") from None
    except (ValueError, KeyError, TypeError):
        db.rollback()
        raise HTTPException(422, "Confirmed planning data could not be safely converted") from None
    except Exception:
        db.rollback()
        raise
    return ConfirmPlanResponse(plan_id=plan_id, created_counts={
        "plans": 1, "resources": len(resources), "tasks": len(tasks),
        "availability": window_count, "requirements": len(draft.requirements),
        "dependencies": len(draft.dependencies),
        "constraints": len(draft.constraints) + bool(draft.custom_fields),
        "disabled_constraints": disabled_count,
    })

"""Explain saved facts and objective terms without re-solving or calling an LLM."""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.models import SolverRun
from app.schemas.explanation import ExplanationReason, PlanExplanation, TaskExplanation
from app.schemas.planning import FullPlanResponse
from app.schemas.solver import SolveResponse
from app.services.solver.input_builder import PRIORITY, build_input, minute_offset

OBJECTIVE_EXPLANATION = [
    "1. Minimize makespan: finish the entire plan as early as possible. This is the dominant objective.",
    "2. Favor earlier completion of higher-priority tasks: low=1, medium=2, high=4, critical=8.",
    "3. Minimize soft penalties for unmet resource and completion-time preferences. "
    "After makespan, the solver minimizes 1000 times weighted priority completion plus scaled soft penalties; "
    "these secondary goals can trade off, rather than having strict precedence.",
]


def explain_latest_run(db, plan):
    run = db.scalar(select(SolverRun).where(SolverRun.plan_id == plan.id)
                    .order_by(SolverRun.id.desc()).limit(1))
    if run is None:
        raise HTTPException(409, detail={"code": "plan_not_solved", "message": "Solve this plan before requesting an explanation."})
    result = SolveResponse.model_validate(run.result)
    response = PlanExplanation(
        plan_id=plan.id, run_id=run.id, status=result.status, summary="",
        objective_explanation=OBJECTIVE_EXPLANATION, objective=result.objective,
        warnings=result.warnings, analysis_url=f"/api/plans/{plan.id}/analysis",
    )
    if result.status in ("infeasible", "unknown"):
        response.summary = (
            "The latest run proved the plan infeasible. No schedule was produced. "
            "See analysis for issues and recovery options."
            if result.status == "infeasible" else
            "The latest run found no schedule and did not prove infeasibility. See analysis for guidance."
        )
        return response

    snapshot = FullPlanResponse.model_validate(run.input_snapshot)
    data = build_input(snapshot)
    scheduled = {item.task_id: item for item in result.schedule}
    tasks = {item.id: item for item in snapshot.tasks}
    resources = {item.id: item for item in snapshot.resources}
    hard = [rule for rule in snapshot.constraints if rule.enabled and rule.hardness == "hard"]
    deadline_tasks = {rule.parameters["task_id"] for rule in hard if rule.constraint_type == "deadline"}
    availability_resources = {rule.parameters["resource_id"] for rule in hard if rule.constraint_type == "availability"}
    anchor = snapshot.plan.planning_start
    response.summary = (
        f"Latest run is {result.status}: {len(result.schedule)} tasks scheduled with a makespan of "
        f"{result.metrics.makespan_minutes} minutes. Reasons describe applicable constraints and observed "
        "assignments, not proof that any single constraint uniquely caused a start time."
    )
    for item in sorted(result.schedule, key=lambda task: (task.start_offset_minutes, task.task_id)):
        task = tasks[item.task_id]
        reasons = []
        def add(kind, message, **kwargs):
            reasons.append(ExplanationReason(kind=kind, message=message, **kwargs))

        for before, after in data.dependencies:
            if after == task.id:
                predecessor = scheduled[before]
                add("dependency", f"Must start after {predecessor.task_name} finishes at {predecessor.end_time.isoformat()}.",
                    related_task_ids=[before], satisfied=item.start_offset_minutes >= predecessor.end_offset_minutes)
        if task.earliest_start is not None:
            lower = anchor + timedelta(minutes=data.earliest[task.id])
            add("earliest_start", f"Cannot start before {lower.isoformat()} (effective minute boundary).",
                satisfied=item.start_offset_minutes >= data.earliest[task.id])
        for requirement in sorted(task.requirements, key=lambda value: value.id):
            candidates = data.candidates[requirement.id]
            add("resource_capacity", f"Requires {requirement.quantity} unit(s) of {requirement.resource_type}; "
                "matching resource capacity must remain available throughout the task.", resource_ids=candidates)
            if requirement.required_resource_id is not None:
                resource = resources[requirement.required_resource_id]
                add("specific_resource", f"Requires {resource.name} specifically, not any interchangeable resource.",
                    resource_ids=[resource.id], satisfied=any(a.resource_id == resource.id for a in item.assigned_resources))
        for assignment in sorted(item.assigned_resources, key=lambda value: value.resource_id):
            resource = resources[assignment.resource_id]
            add("resource_capacity", f"Assigned {assignment.units} unit(s) of {resource.name}; effective shared capacity "
                f"is {data.capacities[resource.id]} across simultaneous tasks.", resource_ids=[resource.id])
            if resource.availability or resource.id in availability_resources:
                windows = data.windows[resource.id]
                descriptions = "; ".join(
                    f"{(anchor + timedelta(minutes=a)).isoformat()} to {(anchor + timedelta(minutes=b)).isoformat()}"
                    for a, b in windows)
                add("resource_availability", f"{resource.name} must cover the entire task within an effective availability window: {descriptions}.",
                    resource_ids=[resource.id], satisfied=any(a <= item.start_offset_minutes and item.end_offset_minutes <= b for a, b in windows))
        if task.deadline is not None or task.id in deadline_tasks:
            deadline = anchor + timedelta(minutes=data.deadlines[task.id])
            add("deadline", f"Must finish by {deadline.isoformat()}; saved schedule has "
                f"{data.deadlines[task.id] - item.end_offset_minutes} minute(s) of deadline slack.",
                satisfied=item.end_offset_minutes <= data.deadlines[task.id])
        add("priority", f"Priority {task.priority} has completion weight {PRIORITY[task.priority]}. "
            "The objective favors earlier completion, subject to constraints and other objective terms; it does not guarantee task order.")
        for kind, params, weight in data.preferences:
            if params.task_id != task.id:
                continue
            if kind == "preferred_resource":
                met = any(a.resource_id == params.resource_id for a in item.assigned_resources)
                add("soft_preference", f"Prefer {resources[params.resource_id].name}; "
                    f"saved assignment {'meets' if met else 'does not meet'} this preference (scaled penalty {0 if met else weight}).",
                    resource_ids=[params.resource_id], satisfied=met)
            else:
                target = max(0, min(data.horizon, minute_offset(params.preferred_before, anchor)))
                late = max(0, item.end_offset_minutes - target)
                add("soft_preference", f"Prefer completion by {(anchor + timedelta(minutes=target)).isoformat()}; "
                    f"{late} minute(s) late (scaled penalty {late * weight}).", satisfied=late == 0)
        response.tasks.append(TaskExplanation(task_id=task.id, task_name=item.task_name,
            start_time=item.start_time, end_time=item.end_time, reasons=reasons))
    return response

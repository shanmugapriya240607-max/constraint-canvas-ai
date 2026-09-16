from datetime import timedelta
from sqlalchemy import select
from app.models import SolverRun
from app.schemas.analysis import (
    Issue, RecoveryOption, Risk, Bottleneck, HealthFactor, PlanHealth, PlanAnalysisResponse
)
from app.services.planning import full_plan


def _get_latest_solver_run(db, plan_id: int):
    return db.scalar(
        select(SolverRun).where(SolverRun.plan_id == plan_id).order_by(SolverRun.id.desc()).limit(1)
    )


def analyze_infeasibility(snapshot) -> tuple[list[Issue], list[RecoveryOption]]:
    issues = []
    recovery_options = []
    
    plan = snapshot.plan
    plan_window_minutes = int((plan.planning_end - plan.planning_start).total_seconds() / 60)
    
    # Pre-compute resource capacities and types
    type_capacity = {}
    resource_map = {}
    for r in snapshot.resources:
        if r.active:
            type_capacity[r.resource_type] = type_capacity.get(r.resource_type, 0) + r.capacity
            resource_map[r.id] = r
            
    # Dependency graph
    successors = {}
    predecessors = {}
    for d in snapshot.dependencies:
        successors.setdefault(d.before_task_id, []).append(d.after_task_id)
        predecessors.setdefault(d.after_task_id, []).append(d.before_task_id)

    task_map = {t.id: t for t in snapshot.tasks}

    for task in snapshot.tasks:
        # 3. task duration exceeds planning window
        if task.duration_minutes > plan_window_minutes:
            issues.append(Issue(
                type="duration_exceeds_window",
                severity="critical",
                task_id=task.id,
                message=f"Task '{task.name}' duration ({task.duration_minutes}m) exceeds the entire planning window ({plan_window_minutes}m)."
            ))
            recovery_options.append(RecoveryOption(
                title="Extend Planning Window",
                explanation=f"The planning window is too short for task '{task.name}'.",
                changes_required=f"Extend planning_end by at least {task.duration_minutes - plan_window_minutes} minutes.",
                affected_entities=["plan"]
            ))

        # 4. impossible deadline
        if task.deadline:
            start_ref = task.earliest_start if task.earliest_start else plan.planning_start
            available_time = int((task.deadline - start_ref).total_seconds() / 60)
            if task.duration_minutes > available_time:
                issues.append(Issue(
                    type="impossible_deadline",
                    severity="critical",
                    task_id=task.id,
                    message=f"Task '{task.name}' requires {task.duration_minutes}m but only {available_time}m available before its deadline."
                ))
                shortage = task.duration_minutes - available_time
                recovery_options.append(RecoveryOption(
                    title="Extend Deadline",
                    explanation=f"Task '{task.name}' cannot complete before its deadline.",
                    changes_required=f"Extend the deadline by at least {shortage} minutes.",
                    affected_entities=[task.id]
                ))

        # 5. dependency + deadline conflict (simple heuristic)
        if task.deadline and task.id in predecessors:
            for pred_id in predecessors[task.id]:
                pred = task_map.get(pred_id)
                if pred:
                    pred_start = pred.earliest_start if pred.earliest_start else plan.planning_start
                    min_time_needed = pred.duration_minutes + task.duration_minutes
                    available_time = int((task.deadline - pred_start).total_seconds() / 60)
                    if min_time_needed > available_time:
                        issues.append(Issue(
                            type="dependency_deadline_conflict",
                            severity="critical",
                            task_id=task.id,
                            message=f"Task '{task.name}' and predecessor '{pred.name}' require {min_time_needed}m, which exceeds deadline."
                        ))
                        shortage = min_time_needed - available_time
                        recovery_options.append(RecoveryOption(
                            title="Extend Deadline for Dependency",
                            explanation=f"The dependency chain into '{task.name}' is too long for the deadline.",
                            changes_required=f"Extend the deadline by at least {shortage} minutes or shorten predecessor duration.",
                            affected_entities=[task.id, pred.id]
                        ))
                        
        for req in task.requirements:
            # 7. required resource type unavailable
            if req.resource_type not in type_capacity and req.required_resource_id is None:
                issues.append(Issue(
                    type="resource_type_unavailable",
                    severity="critical",
                    task_id=task.id,
                    message=f"Task '{task.name}' requires '{req.resource_type}', but no such active resource exists."
                ))
                recovery_options.append(RecoveryOption(
                    title="Add Required Resource Type",
                    explanation=f"No resources of type '{req.resource_type}' are available.",
                    changes_required=f"Create an active resource of type '{req.resource_type}'.",
                    affected_entities=["resources"]
                ))
            # 1. resource capacity shortage (type-level)
            elif req.required_resource_id is None and req.quantity > type_capacity.get(req.resource_type, 0):
                avail = type_capacity.get(req.resource_type, 0)
                issues.append(Issue(
                    type="resource_capacity",
                    severity="critical",
                    task_id=task.id,
                    message=f"Task '{task.name}' requires {req.quantity} '{req.resource_type}' but only {avail} available.",
                    required=req.quantity,
                    available=avail
                ))
                recovery_options.append(RecoveryOption(
                    title="Increase Resource Capacity",
                    explanation=f"Not enough capacity for type '{req.resource_type}'.",
                    changes_required=f"Add at least {req.quantity - avail} capacity to '{req.resource_type}'.",
                    affected_entities=["resources"]
                ))

            # 2. specific required resource unavailable
            if req.required_resource_id is not None:
                spec_res = resource_map.get(req.required_resource_id)
                if not spec_res or not spec_res.active:
                    issues.append(Issue(
                        type="specific_resource_unavailable",
                        severity="critical",
                        task_id=task.id,
                        message=f"Task '{task.name}' requires specific resource ID {req.required_resource_id} which is unavailable."
                    ))
                    recovery_options.append(RecoveryOption(
                        title="Activate Specific Resource",
                        explanation="The specifically requested resource is missing or inactive.",
                        changes_required="Activate the resource or remove the specific requirement.",
                        affected_entities=[task.id, req.required_resource_id]
                    ))
                elif req.quantity > spec_res.capacity:
                    issues.append(Issue(
                        type="resource_capacity",
                        severity="critical",
                        task_id=task.id,
                        message=f"Task '{task.name}' requires {req.quantity} from '{spec_res.name}' but it only has {spec_res.capacity}.",
                        required=req.quantity,
                        available=spec_res.capacity
                    ))
                    recovery_options.append(RecoveryOption(
                        title="Increase Specific Resource Capacity",
                        explanation=f"Resource '{spec_res.name}' cannot fulfill the quantity requested.",
                        changes_required=f"Increase '{spec_res.name}' capacity to {req.quantity} or lower requirement.",
                        affected_entities=[req.required_resource_id, task.id]
                    ))
                else:
                    # 6. availability window too short
                    if spec_res.availability:
                        max_window = 0
                        for avail in spec_res.availability:
                            window = int((avail.available_until - avail.available_from).total_seconds() / 60)
                            if window > max_window:
                                max_window = window
                        if task.duration_minutes > max_window:
                            issues.append(Issue(
                                type="availability_window_too_short",
                                severity="critical",
                                task_id=task.id,
                                message=f"Task '{task.name}' needs {task.duration_minutes}m, but '{spec_res.name}' max availability window is {max_window}m."
                            ))
                            recovery_options.append(RecoveryOption(
                                title="Extend Resource Availability",
                                explanation=f"Resource '{spec_res.name}' is not available long enough continuously.",
                                changes_required=f"Extend an availability window to at least {task.duration_minutes} minutes.",
                                affected_entities=[req.required_resource_id]
                            ))

    # Deduplicate issues/recovery by turning into dict then back to list based on tuple of fields
    unique_issues = { (i.type, i.task_id): i for i in issues }.values()
    unique_recovery = { r.title: r for r in recovery_options }.values()
    
    return list(unique_issues), list(unique_recovery)


def analyze_risks_and_bottlenecks(snapshot, run) -> tuple[list[Risk], list[Bottleneck], list[HealthFactor]]:
    risks = []
    bottlenecks = []
    factors = []
    
    if not run or not run.result or 'schedule' not in run.result:
        return risks, bottlenecks, factors
        
    schedule = run.result['schedule']
    plan_window_minutes = int((snapshot.plan.planning_end - snapshot.plan.planning_start).total_seconds() / 60)
    makespan = run.result.get('metrics', {}).get('makespan_minutes', plan_window_minutes) or plan_window_minutes
    
    task_map = {t.id: t for t in snapshot.tasks}
    
    # 1. Low deadline slack
    from datetime import datetime
    for st in schedule:
        task = task_map.get(st['task_id'])
        if task and task.deadline:
            end_time = datetime.fromisoformat(st['end_time'].replace("Z", "+00:00"))
            slack_minutes = int((task.deadline - end_time).total_seconds() / 60)
            if 0 <= slack_minutes <= 15:
                risks.append(Risk(
                    task_id=task.id,
                    message=f"Task '{task.name}' has only {slack_minutes} minutes of deadline slack."
                ))
                factors.append(HealthFactor(name="Deadline slack", impact=-8, reason=f"Task '{task.name}' has low deadline slack ({slack_minutes}m)."))
                
    # Dependency chains
    successors = {}
    for d in snapshot.dependencies:
        successors.setdefault(d.before_task_id, []).append(d.after_task_id)
        
    for task_id, succs in successors.items():
        if len(succs) >= 3:
            task = task_map.get(task_id)
            bottlenecks.append(Bottleneck(
                type="task",
                task_id=task_id,
                name=task.name if task else str(task_id),
                reason=f"Task is a dependency for {len(succs)} other tasks."
            ))
            factors.append(HealthFactor(name="Dependency risk", impact=-5, reason=f"Task '{task.name}' blocks {len(succs)} other tasks."))
            
    # Resource utilization
    res_usage_minutes = {}
    for st in schedule:
        for ar in st.get('assigned_resources', []):
            # approximate: tasks takes duration_minutes * units of resource effort
            # but for purely time utilization we just use duration
            res_usage_minutes[ar['resource_id']] = res_usage_minutes.get(ar['resource_id'], 0) + st['duration_minutes']
            
    for r in snapshot.resources:
        if r.id in res_usage_minutes:
            utilization = (res_usage_minutes[r.id] / makespan) * 100 if makespan > 0 else 0
            if utilization > 90:
                risks.append(Risk(
                    message=f"Resource '{r.name}' has very high utilization ({utilization:.1f}%)."
                ))
                bottlenecks.append(Bottleneck(
                    type="resource",
                    resource_id=r.id,
                    name=r.name,
                    utilization_percent=round(utilization, 1),
                    reason=f"Resource is used for {utilization:.1f}% of the makespan."
                ))
                factors.append(HealthFactor(name="Resource overload", impact=-10, reason=f"Resource '{r.name}' is over 90% utilized."))
                
    return risks, bottlenecks, factors


def analyze_snapshot(snapshot, run, status: str) -> PlanAnalysisResponse:
    issues = []
    recovery_options = []
    risks = []
    bottlenecks = []
    factors = []
    score = 100
    
    inf_issues, inf_recovery = analyze_infeasibility(snapshot)
    
    if status == "infeasible" or not run or run.solver_status == "infeasible":
        issues = inf_issues
        recovery_options = inf_recovery
        score = 20
        factors.append(HealthFactor(name="Infeasibility", impact=-80, reason="The plan cannot be scheduled with current constraints."))
        grade = "critical"
    else:
        risks, bottlenecks, dyn_factors = analyze_risks_and_bottlenecks(snapshot, run)
        factors.extend(dyn_factors)
        
        for f in factors:
            score += f.impact
            
        if score > 100:
            score = 100
        if score < 0:
            score = 0
            
        if score >= 80:
            grade = "good"
        elif score >= 50:
            grade = "fair"
        elif score >= 20:
            grade = "poor"
        else:
            grade = "critical"
            
    return PlanAnalysisResponse(
        plan_id=snapshot.plan.id,
        status=status,
        issues=issues,
        recovery_options=recovery_options,
        risks=risks,
        bottlenecks=bottlenecks,
        health=PlanHealth(score=score, grade=grade, factors=factors)
    )

def analyze_plan(db, plan) -> PlanAnalysisResponse:
    run = _get_latest_solver_run(db, plan.id)
    snapshot = full_plan(db, plan)
    status = run.solver_status if run else plan.status
    return analyze_snapshot(snapshot, run, status)

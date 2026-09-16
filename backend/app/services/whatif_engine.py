from copy import deepcopy
from typing import Any
from fastapi import HTTPException
from app.models import SolverRun
from app.schemas.planning import FullPlanResponse, ResourceFull, TaskFull
from app.schemas.whatif import (
    WhatIfRequest, WhatIfResponse, ScenarioMetrics, WhatIfImpact,
    CompareScenariosRequest, ScenarioComparisonResponse, ComparedScenarioMetrics,
    AddTemporaryResourceChange
)
from app.services.planning import full_plan
from app.services.solver.service import solve_plan, solve
from app.services.solver.input_builder import build_input, SolverInputError
from app.schemas.solver import SolveRequest
from app.services.analysis_engine import _get_latest_solver_run, analyze_snapshot


def _get_baseline(db, plan) -> tuple[FullPlanResponse, Any]:
    snapshot = full_plan(db, plan)
    run = _get_latest_solver_run(db, plan.id)
    if not run:
        result = solve_plan(db, plan, SolveRequest())
        run = _get_latest_solver_run(db, plan.id)
    return snapshot, run


def apply_changes(snapshot: FullPlanResponse, changes: list) -> FullPlanResponse:
    # Deep copy to ensure we do not mutate the original snapshot
    s = snapshot.model_copy(deep=True)
    
    resource_map = {r.id: r for r in s.resources}
    task_map = {t.id: t for t in s.tasks}
    
    temp_resource_id_counter = -1
    
    for c in changes:
        if c.type == "resource_unavailable":
            if c.resource_id not in resource_map:
                raise HTTPException(status_code=400, detail=f"Unknown resource_id {c.resource_id}")
            resource_map[c.resource_id].active = False
            
        elif c.type == "resource_capacity_change":
            if c.resource_id not in resource_map:
                raise HTTPException(status_code=400, detail=f"Unknown resource_id {c.resource_id}")
            resource_map[c.resource_id].capacity = c.capacity
            
        elif c.type == "deadline_change":
            if c.task_id not in task_map:
                raise HTTPException(status_code=400, detail=f"Unknown task_id {c.task_id}")
            task_map[c.task_id].deadline = c.deadline
            
        elif c.type == "priority_change":
            if c.task_id not in task_map:
                raise HTTPException(status_code=400, detail=f"Unknown task_id {c.task_id}")
            task_map[c.task_id].priority = c.priority
            
        elif c.type == "task_duration_change":
            if c.task_id not in task_map:
                raise HTTPException(status_code=400, detail=f"Unknown task_id {c.task_id}")
            task_map[c.task_id].duration_minutes = c.duration_minutes
            
        elif c.type == "resource_availability_change":
            if c.resource_id not in resource_map:
                raise HTTPException(status_code=400, detail=f"Unknown resource_id {c.resource_id}")
            res = resource_map[c.resource_id]
            res.availability = [] # simplify by clearing and adding a new window for simulation
            # The schema defines availability as a list of AvailabilityResponse, but it has id etc.
            # We can just push a fake one since the solver input builder might only care about available_from/until.
            from app.schemas.planning import AvailabilityResponse
            from datetime import datetime, timezone
            res.availability.append(AvailabilityResponse(
                id=-1, resource_id=res.id, available_from=c.available_from, available_until=c.available_until
            ))
            
        elif c.type == "add_temporary_resource":
            from datetime import datetime, timezone
            from decimal import Decimal
            temp_res = ResourceFull(
                id=temp_resource_id_counter,
                plan_id=s.plan.id,
                name=c.name,
                resource_type=c.resource_type,
                capacity=c.capacity,
                cost_per_hour=None,
                active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                availability=[]
            )
            s.resources.append(temp_res)
            resource_map[temp_res.id] = temp_res
            temp_resource_id_counter -= 1
            
    return s


def simulate_scenario_logic(baseline_snapshot: FullPlanResponse, changes: list):
    s = apply_changes(baseline_snapshot, changes)
    try:
        input_data = build_input(s)
        result = solve(input_data, max_solve_seconds=10.0)
        
        class FakeRun:
            def __init__(self, res):
                self.solver_status = res.status
                self.result_data = res.model_dump(mode="json")
            @property
            def result(self):
                return self.result_data
                
        fake_run = FakeRun(result)
        analysis = analyze_snapshot(s, fake_run, result.status)
        return result, analysis
    except SolverInputError as exc:
        from app.schemas.solver import SolveResponse, SolveMetrics
        result = SolveResponse(
            plan_id=s.plan.id,
            status="infeasible",
            metrics=SolveMetrics(
                makespan_minutes=None, 
                solver_wall_time_ms=0,
                task_count=len(s.tasks),
                scheduled_task_count=0,
                planning_horizon_minutes=0
            ),
            schedule=[],
            warnings=[]
        )
        analysis = analyze_snapshot(s, None, "infeasible")
        return result, analysis


def simulate_what_if(db, plan, request: WhatIfRequest) -> WhatIfResponse:
    snapshot, run = _get_baseline(db, plan)
    
    baseline_analysis = analyze_snapshot(snapshot, run, run.solver_status if run else plan.status)
    
    baseline_metrics = ScenarioMetrics(
        status=baseline_analysis.status,
        makespan_minutes=run.result.get("metrics", {}).get("makespan_minutes") if run and run.result else None,
        deadline_violations=len([i for i in baseline_analysis.issues if i.type == "impossible_deadline" or i.type == "dependency_deadline_conflict"]),
        health_score=baseline_analysis.health.score
    )
    
    result, analysis = simulate_scenario_logic(snapshot, request.changes)
    
    scenario_metrics = ScenarioMetrics(
        status=analysis.status,
        makespan_minutes=result.metrics.makespan_minutes if result.status in ("optimal", "feasible") else None,
        deadline_violations=len([i for i in analysis.issues if i.type == "impossible_deadline" or i.type == "dependency_deadline_conflict"]),
        health_score=analysis.health.score
    )
    
    base_issue_keys = {(i.type, i.task_id) for i in baseline_analysis.issues}
    new_issue_keys = {(i.type, i.task_id) for i in analysis.issues}
    
    added_keys = new_issue_keys - base_issue_keys
    resolved_keys = base_issue_keys - new_issue_keys
    
    new_issues = [i for i in analysis.issues if (i.type, i.task_id) in added_keys]
    resolved_issues = [i for i in baseline_analysis.issues if (i.type, i.task_id) in resolved_keys]
    
    makespan_change = None
    if baseline_metrics.makespan_minutes is not None and scenario_metrics.makespan_minutes is not None:
        makespan_change = scenario_metrics.makespan_minutes - baseline_metrics.makespan_minutes
        
    impact = WhatIfImpact(
        makespan_change_minutes=makespan_change,
        health_change=scenario_metrics.health_score - baseline_metrics.health_score,
        new_issues=new_issues,
        resolved_issues=resolved_issues
    )
    
    return WhatIfResponse(
        plan_id=plan.id,
        baseline=baseline_metrics,
        scenario=scenario_metrics,
        changes=request.changes,
        impact=impact,
        schedule=result.schedule if result.status in ("optimal", "feasible") else []
    )


def compare_scenarios(db, plan, request: CompareScenariosRequest) -> ScenarioComparisonResponse:
    snapshot, run = _get_baseline(db, plan)
    
    baseline_analysis = analyze_snapshot(snapshot, run, run.solver_status if run else plan.status)
    baseline_metrics = ScenarioMetrics(
        status=baseline_analysis.status,
        makespan_minutes=run.result.get("metrics", {}).get("makespan_minutes") if run and run.result else None,
        deadline_violations=len([i for i in baseline_analysis.issues if i.type == "impossible_deadline" or i.type == "dependency_deadline_conflict"]),
        health_score=baseline_analysis.health.score
    )
    
    compared_scenarios = []
    
    for sc in request.scenarios:
        result, analysis = simulate_scenario_logic(snapshot, sc.changes)
        
        compared_scenarios.append(ComparedScenarioMetrics(
            name=sc.name,
            status=analysis.status,
            makespan_minutes=result.metrics.makespan_minutes if result.status in ("optimal", "feasible") else None,
            deadline_violations=len([i for i in analysis.issues if i.type == "impossible_deadline" or i.type == "dependency_deadline_conflict"]),
            health_score=analysis.health.score,
            issues_count=len(analysis.issues)
        ))
        
    return ScenarioComparisonResponse(
        baseline=baseline_metrics,
        scenarios=compared_scenarios
    )

"""CP-SAT semantics, safety, determinism, and authenticated persistence tests."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from ortools.sat.python import cp_model
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Plan, SolverRun, User
from app.schemas.planning import FullPlanResponse
from app.services.solver.cp_sat_solver import solve
from app.services.solver.input_builder import SolverInputError, build_input
from app.services.solver.result_builder import build_result

START = datetime(2026,9,16,9,tzinfo=timezone.utc)


def at(minutes):
    return START + timedelta(minutes=minutes)


def requirement(identifier=1, quantity=1, specific=None, kind="developer", task_id=1):
    return dict(id=identifier,task_id=task_id,resource_type=kind,quantity=quantity,required_resource_id=specific)


def task(identifier=1,duration=60,priority="medium",requirements=None,**kwargs):
    return dict(id=identifier,plan_id=1,name=f"Task {identifier}",description=None,duration_minutes=duration,
                priority=priority,earliest_start=None,deadline=None,created_at=START,updated_at=START,
                requirements=requirements or [],**{}) | kwargs


def resource(identifier=1,capacity=1,windows=None,**kwargs):
    availability = [dict(id=i+1,resource_id=identifier,available_from=at(a),available_until=at(b))
                    for i,(a,b) in enumerate(windows or [])]
    return dict(id=identifier,plan_id=1,name=f"Resource {identifier}",resource_type="developer",capacity=capacity,
                cost_per_hour=None,active=True,created_at=START,updated_at=START,availability=availability) | kwargs


def rule(kind,parameters,hardness="hard",weight=None,identifier=1,enabled=True):
    return dict(id=identifier,plan_id=1,constraint_type=kind,hardness=hardness,weight=weight,parameters=json.loads(json.dumps(parameters,default=lambda item:item.isoformat())),
                source="manual",enabled=enabled,created_at=START,updated_at=START)


def snapshot(tasks=None,resources=None,edges=None,rules=None,horizon=540):
    return FullPlanResponse.model_validate(dict(
        plan=dict(id=1,name="Test plan",description=None,planning_start=START,planning_end=at(horizon),
                  status="draft",created_at=START,updated_at=START),
        tasks=tasks if tasks is not None else [task()],resources=resources or [],
        dependencies=[dict(id=i+1,plan_id=1,before_task_id=a,after_task_id=b) for i,(a,b) in enumerate(edges or [])],
        constraints=rules or [],
    ))


def run(problem):
    data = build_input(problem)
    result = solve(data,2)
    if result.status in ("optimal","feasible"):
        audit(data,result)
    return result


def audit(data,result):
    """Independent result checks, supplementary to constraints inside CP-SAT."""
    entries = {entry.task_id:entry for entry in result.schedule}
    assert len(entries) == len(data.snapshot.tasks)
    load = {resource.id:[0]*data.horizon for resource in data.snapshot.resources}
    resource_map = {resource.id:resource for resource in data.snapshot.resources}
    for original in data.snapshot.tasks:
        entry = entries[original.id]
        assert entry.end_offset_minutes-entry.start_offset_minutes == original.duration_minutes
        assert 0 <= entry.start_offset_minutes < entry.end_offset_minutes <= data.horizon
        assert entry.start_offset_minutes >= data.earliest[original.id]
        assert entry.end_offset_minutes <= data.deadlines[original.id]
        assert entry.start_time == data.snapshot.plan.planning_start+timedelta(minutes=entry.start_offset_minutes)
        assert sum(item.units for item in entry.assigned_resources) == sum(req.quantity for req in original.requirements)
        for assignment in entry.assigned_resources:
            assert resource_map[assignment.resource_id].active and assignment.units > 0
            assert any(a <= entry.start_offset_minutes and entry.end_offset_minutes <= b for a,b in data.windows[assignment.resource_id])
            for minute in range(entry.start_offset_minutes,entry.end_offset_minutes):
                load[assignment.resource_id][minute] += assignment.units
        for req in original.requirements:
            if req.required_resource_id:
                assert sum(item.units for item in entry.assigned_resources if item.resource_id == req.required_resource_id) >= req.quantity
            else:
                assert sum(item.units for item in entry.assigned_resources if item.resource_type.strip().casefold() == req.resource_type.strip().casefold()) >= req.quantity
    for before,after in data.dependencies:
        assert entries[after].start_offset_minutes >= entries[before].end_offset_minutes
    for rid,values in load.items():
        assert max(values,default=0) <= data.capacities[rid]
        if rid in data.max_work_minutes:
            assert sum(values) <= data.max_work_minutes[rid]


def test_single_task_no_resource():
    result = run(snapshot())
    assert result.status == "optimal" and result.objective.makespan_minutes == 60
    assert result.schedule[0].assigned_resources == []


def test_independent_tasks_parallel():
    result = run(snapshot(tasks=[task(1,60),task(2,90)]))
    assert result.objective.makespan_minutes == 90
    assert [item.start_offset_minutes for item in result.schedule] == [0,0]


def test_dependencies_deadline_and_earliest_start():
    result = run(snapshot(tasks=[task(1,60,earliest_start=at(30)),task(2,45,deadline=at(150))],edges=[(1,2)]))
    assert result.objective.makespan_minutes == 135


def test_impossible_hard_deadline_is_infeasible():
    result = run(snapshot(tasks=[task(1,60,deadline=at(30))]))
    assert result.status == "infeasible" and result.schedule == [] and result.objective is None


@pytest.mark.parametrize("capacity,makespan",[(1,120),(2,60)])
def test_capacity_enforced_in_model(capacity,makespan):
    tasks = [task(i,requirements=[requirement(i,task_id=i)]) for i in (1,2)]
    result = run(snapshot(tasks=tasks,resources=[resource(capacity=capacity)]))
    assert result.objective.makespan_minutes == makespan


@pytest.mark.parametrize("resources",[[resource(1),resource(2)],[resource(1,capacity=2)]])
def test_generic_quantity_two_allocates_units(resources):
    result = run(snapshot(tasks=[task(requirements=[requirement(quantity=2)])],resources=resources))
    assert sum(item.units for item in result.schedule[0].assigned_resources) == 2


def test_specific_resource_not_substituted():
    result = run(snapshot(tasks=[task(requirements=[requirement(specific=2)])],resources=[resource(1),resource(2)]))
    assert result.schedule[0].assigned_resources[0].resource_id == 2


def test_capacity_shortage_proven_infeasible():
    result = run(snapshot(tasks=[task(requirements=[requirement(quantity=3)])],resources=[resource(capacity=2)]))
    assert result.status == "infeasible" and result.schedule == []


def test_requirements_additive_not_double_counted():
    problem = snapshot(tasks=[task(requirements=[requirement(1),requirement(2)])],resources=[resource(capacity=1)])
    assert run(problem).status == "infeasible"


def test_type_matching_and_inactive_exclusion():
    problem = snapshot(tasks=[task(requirements=[requirement(kind=" Developer ")])],resources=[resource(1,resource_type="vehicle"),resource(2,active=False),resource(3)])
    assert run(problem).schedule[0].assigned_resources[0].resource_id == 3


@pytest.mark.parametrize("resources,req",[
    ([resource(resource_type="vehicle")],requirement()),
    ([resource(active=False)],requirement(specific=1)),
    ([resource()],requirement(specific=99)),
    ([resource(resource_type="vehicle")],requirement(specific=1)),
])
def test_invalid_resource_references(resources,req):
    with pytest.raises(SolverInputError):
        run(snapshot(tasks=[task(requirements=[req])],resources=resources))


def test_no_windows_means_entire_plan():
    result = run(snapshot(tasks=[task(1,300,requirements=[requirement(specific=1)])],resources=[resource()]))
    assert result.status == "optimal" and result.schedule[0].end_offset_minutes == 300


@pytest.mark.parametrize("windows,duration,earliest,expected",[
    ([(0,240),(300,480)],120,210,300),
    ([(0,240),(300,480)],240,0,0),
    ([(0,240),(300,480)],300,0,None),
    ([(600,700)],60,0,None),
])
def test_windows_never_cross_gaps(windows,duration,earliest,expected):
    result = run(snapshot(tasks=[task(1,duration,earliest_start=at(earliest),requirements=[requirement(specific=1)])],resources=[resource(windows=windows),resource(2)]))
    if expected is None:
        assert result.status == "infeasible"
    else:
        assert result.schedule[0].start_offset_minutes == expected


def test_original_expo_scenario_is_infeasible():
    tasks = [task(1,180,"high",[requirement(1,2)]),task(2,90,"critical",[requirement(2,specific=1,task_id=2)],deadline=at(420)),task(3,45)]
    resources = [resource(1,windows=[(0,240)]),resource(2),resource(3,capacity=2)]
    assert run(snapshot(tasks=tasks,resources=resources,edges=[(1,2)])).status == "infeasible"


def test_minimally_corrected_expo_scenario():
    tasks = [task(1,180,"high",[requirement(1,2)]),task(2,90,"critical",[requirement(2,specific=1,task_id=2)],deadline=at(420)),task(3,45)]
    resources = [resource(1,windows=[(0,270)]),resource(2),resource(3,capacity=2)]
    result = run(snapshot(tasks=tasks,resources=resources,edges=[(1,2)]))
    assert result.status == "optimal" and result.objective.makespan_minutes == 270


def test_critical_priority_influences_completion_order():
    result = run(snapshot(tasks=[task(1,60,"low",[requirement(1)]),task(2,60,"critical",[requirement(2,task_id=2)])],resources=[resource()]))
    assert [entry.task_id for entry in result.schedule] == [2,1]


def test_priority_is_not_hard_ordering():
    result = run(snapshot(tasks=[task(1,60,"low",[requirement(1)]),task(2,60,"critical",[requirement(2,task_id=2)],earliest_start=at(120))],resources=[resource()]))
    assert [entry.task_id for entry in result.schedule] == [1,2]


def test_preferred_resource_changes_assignment():
    result = run(snapshot(tasks=[task(requirements=[requirement()])],resources=[resource(1),resource(2)],
        rules=[rule("preferred_resource",{"task_id":1,"resource_id":2},"soft",1)]))
    assert result.schedule[0].assigned_resources[0].resource_id == 2
    assert result.objective.soft_penalty_scaled == 0


def test_impossible_soft_resource_does_not_break_feasibility():
    result = run(snapshot(tasks=[task(requirements=[requirement()])],resources=[resource(1),resource(2,active=False)],
        rules=[rule("preferred_resource",{"task_id":1,"resource_id":2},"soft",3)]))
    assert result.status == "optimal" and result.objective.soft_penalty_scaled == 3000


def test_preferred_time_weight_affects_objective_not_feasibility():
    tasks = [task(1,60,"medium",[requirement(1)]),task(2,60,"medium",[requirement(2,task_id=2)])]
    result = run(snapshot(tasks=tasks,resources=[resource()],rules=[rule("preferred_time",{"task_id":2,"preferred_before":at(30)},"soft",5)]))
    assert result.schedule[0].task_id == 2
    assert result.objective.soft_penalty_scaled == 150000


@pytest.mark.parametrize("kind,parameters,expected",[
    ("deadline",{"task_id":1,"deadline":at(30)},"infeasible"),
    ("resource_capacity",{"resource_id":1,"capacity":0},"infeasible"),
    ("availability",{"resource_id":1,"available_from":at(120),"available_until":at(150)},"infeasible"),
    ("max_work_hours",{"resource_id":1,"max_hours":"0.5"},"infeasible"),
])
def test_safe_hard_rules_enforced(kind,parameters,expected):
    result = run(snapshot(tasks=[task(requirements=[requirement(specific=1)])],resources=[resource()],rules=[rule(kind,parameters)]))
    assert result.status == expected


def test_hard_dependency_rule():
    result = run(snapshot(tasks=[task(1),task(2)],rules=[rule("dependency",{"before_task_id":1,"after_task_id":2})]))
    assert result.objective.makespan_minutes == 120


def test_max_work_counts_capacity_units():
    problem = snapshot(tasks=[task(requirements=[requirement(quantity=2)])],resources=[resource(capacity=2)],
        rules=[rule("max_work_hours",{"resource_id":1,"max_hours":1})])
    assert run(problem).status == "infeasible"


def test_hard_availability_intersects_existing_windows():
    result = run(snapshot(tasks=[task(1,60,requirements=[requirement()])],resources=[resource(windows=[(0,120),(180,300)])],
        rules=[rule("availability",{"resource_id":1,"available_from":at(90),"available_until":at(270)})]))
    assert result.schedule[0].start_offset_minutes == 180


def test_hard_capacity_never_increases_stored_capacity():
    tasks = [task(i,requirements=[requirement(i,task_id=i)]) for i in (1,2)]
    result = run(snapshot(tasks=tasks,resources=[resource()],rules=[rule("resource_capacity",{"resource_id":1,"capacity":2})]))
    assert result.objective.makespan_minutes == 120


@pytest.mark.parametrize("problem",[
    snapshot(tasks=[]),snapshot(tasks=[task(duration=600)]),snapshot(tasks=[task(deadline=at(-1))]),
    snapshot(tasks=[task(1),task(2)],edges=[(1,2),(2,1)]),snapshot(edges=[(1,99)]),
    snapshot(rules=[rule("custom",{"expression":"__import__('os').system('never execute')"})]),
    snapshot(rules=[rule("deadline",{"task_id":99,"deadline":at(60)})]),
    snapshot(rules=[rule("deadline",{"task_id":1,"deadline":at(60),"unknown":True})]),
    snapshot(rules=[rule("preferred_resource",{"task_id":1,"resource_id":99},"soft",1)]),
])
def test_invalid_inputs_are_not_infeasibility(problem):
    with pytest.raises(SolverInputError):
        run(problem)


def test_disabled_hard_and_unsupported_soft_handling():
    result = run(snapshot(rules=[rule("custom",{"code":"not executed"},enabled=False),rule("custom",{},"soft",1,identifier=2)]))
    assert result.status == "optimal" and len(result.warnings) == 1


def test_conservative_subminute_bounds():
    result = run(snapshot(tasks=[task(1,1,earliest_start=START+timedelta(seconds=1),deadline=START+timedelta(minutes=2,seconds=59))]))
    assert result.schedule[0].start_offset_minutes == 1 and result.schedule[0].end_offset_minutes == 2


def test_determinism_same_schedule_and_objective():
    problem = snapshot(tasks=[task(i,30,requirements=[requirement(i,task_id=i)]) for i in range(1,5)],resources=[resource(1),resource(2)])
    first,second = run(problem),run(problem)
    assert first.schedule == second.schedule and first.objective == second.objective


def test_unknown_never_reads_nonexistent_solution():
    class Unsolved:
        wall_time = 0.001
    result = build_result(build_input(snapshot()),None,Unsolved(),cp_model.UNKNOWN)
    assert result.status == "unknown" and result.schedule == [] and result.objective is None


@pytest.fixture
def owner(client,application,db_engine):
    with Session(db_engine) as db:
        user = User(name="Solver owner",email="solver-owner@example.com",password_hash="unused-fixture")
        db.add(user)
        db.commit()
        token = application.state.token_service.issue(user.id)
    return {"Authorization":"Bearer "+token}


@pytest.fixture
def api_plan(client,owner):
    response = client.post("/api/plans",json={"name":"Solver API","planning_start":START.isoformat(),"planning_end":at(540).isoformat()},headers=owner)
    assert response.status_code == 201
    return response.json()


def api_task(client,owner,api_plan,**changes):
    response = client.post(f"/api/plans/{api_plan['id']}/tasks",json={"name":"Work","duration_minutes":60,**changes},headers=owner)
    assert response.status_code == 201
    return response.json()


def test_solve_persists_history_and_status_without_input_changes(client,owner,api_plan,db_engine):
    original = api_task(client,owner,api_plan)
    base = f"/api/plans/{api_plan['id']}"
    first = client.post(base+"/solve",headers=owner)
    assert first.status_code == 200 and first.json()["status"] == "optimal"
    second = client.post(base+"/solve",json={"max_solve_seconds":2},headers=owner)
    assert second.status_code == 200 and second.json()["run_id"] != first.json()["run_id"]
    assert client.get(base,headers=owner).json()["status"] == "solved"
    assert client.get(base+f"/tasks/{original['id']}",headers=owner).json() == original
    history = client.get(base+"/runs",headers=owner).json()
    assert [row["id"] for row in history] == [second.json()["run_id"],first.json()["run_id"]]
    detail = client.get(base+f"/runs/{first.json()['run_id']}",headers=owner).json()
    assert detail["result"] == first.json()
    assert detail["solver_version"] == "9.12.4544"
    client.patch(base+f"/tasks/{original['id']}",json={"duration_minutes":90},headers=owner)
    assert client.get(base+f"/runs/{first.json()['run_id']}",headers=owner).json() == detail
    with Session(db_engine) as db:
        record = db.get(SolverRun,first.json()["run_id"])
        assert record.input_snapshot["tasks"][0]["duration_minutes"] == 60


def test_infeasible_persisted_and_status_updated(client,owner,api_plan):
    api_task(client,owner,api_plan,deadline=at(30).isoformat())
    base = f"/api/plans/{api_plan['id']}"
    result = client.post(base+"/solve",headers=owner).json()
    assert result["status"] == "infeasible" and result["schedule"] == []
    assert client.get(base,headers=owner).json()["status"] == "infeasible"
    assert client.get(base+"/runs",headers=owner).json()[0]["solver_status"] == "infeasible"


@pytest.mark.parametrize("path,method",[("solve","POST"),("runs","GET"),("runs/1","GET")])
def test_solver_routes_reject_anonymous(client,api_plan,path,method):
    assert client.request(method,f"/api/plans/{api_plan['id']}/{path}").status_code == 401


def test_solve_and_history_cross_user_isolation(client,owner,api_plan,application,db_engine):
    api_task(client,owner,api_plan)
    base = f"/api/plans/{api_plan['id']}"
    result = client.post(base+"/solve",headers=owner).json()
    with Session(db_engine) as db:
        other = User(name="Other",email="other-solver@example.com",password_hash="unused")
        db.add(other)
        db.commit()
        headers = {"Authorization":"Bearer "+application.state.token_service.issue(other.id)}
    assert client.post(base+"/solve",headers=headers).status_code == 404
    assert client.get(base+"/runs",headers=headers).status_code == 404
    assert client.get(base+f"/runs/{result['run_id']}",headers=headers).status_code == 404
    own_other = client.post("/api/plans",json={"name":"Another","planning_start":START.isoformat(),"planning_end":at(540).isoformat()},headers=owner).json()
    assert client.get(f"/api/plans/{own_other['id']}/runs/{result['run_id']}",headers=owner).status_code == 404


@pytest.mark.parametrize("limit",[0,-1,31])
def test_solve_time_limit_validated(client,owner,api_plan,limit):
    api_task(client,owner,api_plan)
    assert client.post(f"/api/plans/{api_plan['id']}/solve",json={"max_solve_seconds":limit},headers=owner).status_code == 422


def test_invalid_input_returns_422_without_run_or_status_change(client,owner,api_plan):
    base = f"/api/plans/{api_plan['id']}"
    response = client.post(base+"/solve",headers=owner)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "invalid_solver_input"
    assert client.get(base+"/runs",headers=owner).json() == []
    assert client.get(base,headers=owner).json()["status"] == "draft"


def test_run_cascades_only_with_plan(client,owner,api_plan,db_engine):
    task = api_task(client,owner,api_plan)
    base = f"/api/plans/{api_plan['id']}"
    result = client.post(base+"/solve",headers=owner).json()
    assert client.delete(base+f"/tasks/{task['id']}",headers=owner).status_code == 204
    assert client.get(base+f"/runs/{result['run_id']}",headers=owner).status_code == 200
    assert client.delete(base,headers=owner).status_code == 204
    with Session(db_engine) as db:
        assert db.get(SolverRun,result["run_id"]) is None


def test_demo_size_fifty_tasks_thirty_resources():
    tasks = [task(i,15,requirements=[requirement(i,task_id=i)]) for i in range(1,51)]
    result = run(snapshot(tasks=tasks,resources=[resource(i) for i in range(1,31)]))
    assert result.status in ("optimal","feasible") and len(result.schedule) == 50


def test_unknown_run_persisted_without_changing_status(client,owner,api_plan):
    api_task(client,owner,api_plan)
    from app.schemas.solver import SolveMetrics, SolveResponse
    unknown = SolveResponse(status="unknown",plan_id=api_plan["id"],schedule=[],warnings=["Time limit"],
        metrics=SolveMetrics(task_count=1,scheduled_task_count=0,planning_horizon_minutes=540,makespan_minutes=None,solver_wall_time_ms=1))
    base = f"/api/plans/{api_plan['id']}"
    with patch("app.services.solver.service.solve",return_value=unknown):
        response = client.post(base+"/solve",headers=owner)
    assert response.status_code == 200 and response.json()["status"] == "unknown"
    assert client.get(base,headers=owner).json()["status"] == "draft"
    assert client.get(base+"/runs",headers=owner).json()[0]["solver_status"] == "unknown"


def test_unsupported_hard_rule_api_rejects_without_history(client,owner,api_plan):
    api_task(client,owner,api_plan)
    base = f"/api/plans/{api_plan['id']}"
    assert client.post(base+"/constraints",json={"constraint_type":"custom","parameters":{"code":"never execute"}},headers=owner).status_code == 201
    response = client.post(base+"/solve",headers=owner)
    assert response.status_code == 422 and "unsupported" in response.json()["detail"]["message"]
    assert client.get(base+"/runs",headers=owner).json() == []


def test_corrupt_soft_weight_rejected_safely():
    with pytest.raises(SolverInputError):
        run(snapshot(rules=[rule("preferred_time",{"task_id":1,"preferred_before":at(60)},"soft",None)]))


def test_unsafe_objective_bounds_rejected():
    rules = [rule("preferred_time",{"task_id":1,"preferred_before":at(0)},"soft",1001)]
    with pytest.raises(SolverInputError):
        run(snapshot(rules=rules))

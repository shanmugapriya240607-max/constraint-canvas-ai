from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import SolverRun
from tests.test_analysis import actors, base_plan, post


@pytest.fixture
def saved(client, base_plan):
    plan, headers, base = base_plan
    r = post(client, base + "/resources", {"name": "Ravi", "resource_type": "developer", "capacity": 1}, headers)
    post(client, base + f"/resources/{r['id']}/availability", {"available_from": "2026-09-16T10:00:00Z", "available_until": "2026-09-16T17:00:00Z"}, headers)
    first = post(client, base + "/tasks", {"name": "Development", "duration_minutes": 60}, headers)
    task = post(client, base + "/tasks", {"name": "Testing", "duration_minutes": 90, "priority": "critical",
        "earliest_start": "2026-09-16T10:00:00Z", "deadline": "2026-09-16T17:00:00Z"}, headers)
    post(client, base + f"/tasks/{task['id']}/requirements", {"resource_type": "developer", "quantity": 1, "required_resource_id": r['id']}, headers)
    post(client, base + "/dependencies", {"before_task_id": first['id'], "after_task_id": task['id']}, headers)
    post(client, base + "/constraints", {"constraint_type": "preferred_time", "hardness": "soft", "parameters": {
        "task_id": task['id'], "preferred_before": "2026-09-16T10:00:00Z"}}, headers)
    response = client.post(base + "/solve", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "optimal"
    return base, headers, first, task, r


def read(client, saved):
    response = client.get(saved[0] + "/explanation", headers=saved[1])
    assert response.status_code == 200, response.text
    return response.json()


def reasons(data, task, kind):
    return [r for t in data["tasks"] if t["task_id"] == task["id"] for r in t["reasons"] if r["kind"] == kind]


def test_owner_access_objective(client, saved):
    data = read(client, saved)
    assert data["status"] == "optimal"
    assert len(data["tasks"]) == 2
    assert len(data["objective_explanation"]) == 3
    assert "trade off" in data["objective_explanation"][2]
    assert data["objective"]["makespan_minutes"] == 150


def test_cross_user_anonymous(client, actors, saved):
    assert client.get(saved[0] + "/explanation", headers=actors[1]).status_code == 404
    assert client.get(saved[0] + "/explanation").status_code == 401


def test_never_solved(client, base_plan):
    _, headers, base = base_plan
    response = client.get(base + "/explanation", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "plan_not_solved"


def test_dependency(client, saved):
    reason = reasons(read(client, saved), saved[3], "dependency")[0]
    assert reason["related_task_ids"] == [saved[2]["id"]]
    assert reason["satisfied"] is True
    assert "Development" in reason["message"]


def test_specific_resource(client, saved):
    reason = reasons(read(client, saved), saved[3], "specific_resource")[0]
    assert reason["resource_ids"] == [saved[4]["id"]]
    assert "Ravi" in reason["message"]
    assert reason["satisfied"] is True


def test_priority_deadline(client, saved):
    data = read(client, saved)
    assert "critical" in reasons(data, saved[3], "priority")[0]["message"]
    deadline = reasons(data, saved[3], "deadline")[0]
    assert "17:00:00" in deadline["message"]
    assert deadline["satisfied"] is True


def test_availability_earliest_capacity_soft(client, saved):
    data = read(client, saved)
    assert reasons(data, saved[3], "earliest_start")[0]["satisfied"] is True
    assert reasons(data, saved[3], "resource_availability")[0]["satisfied"] is True
    assert "developer" in reasons(data, saved[3], "resource_capacity")[0]["message"]
    soft = reasons(data, saved[3], "soft_preference")[0]
    assert soft["satisfied"] is False
    assert "90 minute(s) late" in soft["message"]


def test_infeasible_latest_no_fabrication(client, saved):
    base, headers, _, task, _ = saved
    response = client.patch(base + f"/tasks/{task['id']}", headers=headers, json={"deadline": "2026-09-16T10:30:00Z"})
    assert response.status_code == 200
    run = client.post(base + "/solve", headers=headers).json()
    assert run["status"] == "infeasible"
    data = read(client, saved)
    assert data["run_id"] == run["run_id"]
    assert data["status"] == "infeasible"
    assert data["tasks"] == [] and data["objective"] is None
    assert data["analysis_url"] == base + "/analysis"
    assert "recovery" in data["summary"]


def test_deterministic_read_only_snapshot(client, saved, db_engine):
    before = read(client, saved)
    base, headers, _, task, _ = saved
    assert client.patch(base + f"/tasks/{task['id']}", headers=headers, json={"name": "Changed", "priority": "low"}).status_code == 200
    with patch("app.services.solver.cp_sat_solver.solve", side_effect=AssertionError("must not solve")):
        assert read(client, saved) == before
        assert read(client, saved) == before
    with Session(db_engine) as db:
        assert len(db.scalars(select(SolverRun)).all()) == 1


def test_unknown_not_infeasible(client, saved, db_engine):
    with Session(db_engine) as db:
        run = db.scalar(select(SolverRun))
        run.solver_status = "unknown"
        run.result = dict(run.result, status="unknown", schedule=[], objective=None)
        db.commit()
    data = read(client, saved)
    assert data["status"] == "unknown" and data["tasks"] == []
    assert "did not prove infeasibility" in data["summary"]

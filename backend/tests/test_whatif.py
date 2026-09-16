import pytest
from sqlalchemy.orm import Session
from app.models import User, Plan, Resource, Task

START = "2026-09-16T09:00:00+00:00"
END = "2026-09-16T18:00:00+00:00"

def post(client, url, payload, headers):
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code in (200, 201), response.text
    return response.json()

@pytest.fixture
def actors(client, application, db_engine):
    with Session(db_engine) as db:
        users = [User(name=f"Actor {i}", email=f"actor{i}@example.com", password_hash="not-used-for-login") for i in range(2)]
        db.add_all(users)
        db.commit()
        ids = [user.id for user in users]
    return [{"Authorization": "Bearer " + application.state.token_service.issue(user_id)} for user_id in ids]

@pytest.fixture
def base_plan(client, actors):
    plan = post(client, "/api/plans", {"name": "Test Plan", "planning_start": START, "planning_end": END}, actors[0])
    base = f"/api/plans/{plan['id']}"
    
    # Add a simple baseline plan that is feasible
    r1 = post(client, f"{base}/resources", {"name": "Dev", "resource_type": "developer", "capacity": 1}, actors[0])
    t1 = post(client, f"{base}/tasks", {"name": "T1", "duration_minutes": 60, "deadline": "2026-09-16T12:00:00+00:00"}, actors[0])
    post(client, f"{base}/tasks/{t1['id']}/requirements", {"resource_type": "developer", "quantity": 1}, actors[0])
    
    return plan, actors[0], base, r1, t1

def test_anonymous_and_cross_user_rejected(client, actors, base_plan):
    plan, owner_headers, base, r1, t1 = base_plan
    
    # 11. anonymous rejected
    resp = client.post(f"{base}/what-if", json={"changes": []})
    assert resp.status_code == 401
    
    # 12. cross-user rejected
    resp = client.post(f"{base}/what-if", json={"changes": []}, headers=actors[1])
    assert resp.status_code == 404

def test_original_plan_unchanged(client, db_engine, base_plan):
    plan, headers, base, r1, t1 = base_plan
    
    # 7. original database plan remains unchanged
    req = {
        "changes": [
            {"type": "resource_capacity_change", "resource_id": r1["id"], "capacity": 5},
            {"type": "task_duration_change", "task_id": t1["id"], "duration_minutes": 900}
        ]
    }
    resp = client.post(f"{base}/what-if", json=req, headers=headers)
    assert resp.status_code == 200, resp.text
    
    with Session(db_engine) as db:
        res = db.get(Resource, r1["id"])
        assert res.capacity == 1  # unchanged
        tsk = db.get(Task, t1["id"])
        assert tsk.duration_minutes == 60  # unchanged

def test_what_if_changes(client, base_plan):
    plan, headers, base, r1, t1 = base_plan
    
    # 1. resource becomes unavailable
    req = {"changes": [{"type": "resource_unavailable", "resource_id": r1["id"]}]}
    resp = client.post(f"{base}/what-if", json=req, headers=headers).json()
    assert resp["scenario"]["status"] == "infeasible"
    
    # 2. resource capacity increased
    req = {"changes": [{"type": "resource_capacity_change", "resource_id": r1["id"], "capacity": 2}]}
    resp = client.post(f"{base}/what-if", json=req, headers=headers).json()
    assert resp["scenario"]["status"] in ("optimal", "feasible")
    
    # 3. deadline changed
    req = {"changes": [{"type": "deadline_change", "task_id": t1["id"], "deadline": "2026-09-16T09:30:00+00:00"}]} # too tight
    resp = client.post(f"{base}/what-if", json=req, headers=headers).json()
    assert resp["scenario"]["status"] == "infeasible"
    
    # 4. task priority changed
    req = {"changes": [{"type": "priority_change", "task_id": t1["id"], "priority": "critical"}]}
    resp = client.post(f"{base}/what-if", json=req, headers=headers).json()
    assert resp["scenario"]["status"] in ("optimal", "feasible")
    
    # 5. task duration changed
    req = {"changes": [{"type": "task_duration_change", "task_id": t1["id"], "duration_minutes": 120}]}
    resp = client.post(f"{base}/what-if", json=req, headers=headers).json()
    # 8. baseline vs scenario makespan comparison
    assert resp["impact"]["makespan_change_minutes"] > 0
    assert resp["scenario"]["makespan_minutes"] > resp["baseline"]["makespan_minutes"]
    
    # 6. temporary resource added
    req = {"changes": [{"type": "add_temporary_resource", "name": "Temp", "resource_type": "developer", "capacity": 1}]}
    resp = client.post(f"{base}/what-if", json=req, headers=headers).json()
    assert resp["scenario"]["status"] in ("optimal", "feasible")

def test_multiple_scenarios_comparison(client, base_plan):
    plan, headers, base, r1, t1 = base_plan
    
    req = {
        "scenarios": [
            {
                "name": "Unavailable",
                "changes": [{"type": "resource_unavailable", "resource_id": r1["id"]}]
            },
            {
                "name": "Add capacity",
                "changes": [{"type": "resource_capacity_change", "resource_id": r1["id"], "capacity": 2}]
            }
        ]
    }
    
    resp = client.post(f"{base}/compare-scenarios", json=req, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    assert "baseline" in data
    assert len(data["scenarios"]) == 2
    
    # 9. infeasible scenario comparison
    s1 = next(s for s in data["scenarios"] if s["name"] == "Unavailable")
    assert s1["status"] == "infeasible"
    assert s1["makespan_minutes"] is None
    
    # 10. multiple scenarios compared
    s2 = next(s for s in data["scenarios"] if s["name"] == "Add capacity")
    assert s2["status"] in ("optimal", "feasible")

import pytest

START = "2026-09-16T09:00:00+00:00"
END = "2026-09-16T18:00:00+00:00"

def post(client, url, payload, headers):
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


from sqlalchemy.orm import Session
from app.models import User

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
    return plan, actors[0], f"/api/plans/{plan['id']}"


def test_cross_user_analysis_blocked(client, actors, base_plan):
    plan, owner_headers, base = base_plan
    response = client.get(f"{base}/analysis", headers=actors[1])
    assert response.status_code == 404


def test_capacity_shortage_and_recovery(client, base_plan):
    plan, headers, base = base_plan
    post(client, f"{base}/resources", {"name": "Dev", "resource_type": "developer", "capacity": 2}, headers)
    t1 = post(client, f"{base}/tasks", {"name": "T1", "duration_minutes": 60}, headers)
    post(client, f"{base}/tasks/{t1['id']}/requirements", {"resource_type": "developer", "quantity": 3}, headers)
    
    response = client.get(f"{base}/analysis", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    # Assert issues
    assert data["status"] == "draft" # or infeasible if solved
    issues = [i for i in data["issues"] if i["type"] == "resource_capacity"]
    assert len(issues) == 1
    assert issues[0]["task_id"] == t1["id"]
    assert issues[0]["required"] == 3
    assert issues[0]["available"] == 2
    assert "requires 3 'developer' but only 2 available" in issues[0]["message"]
    
    # Assert recovery
    recoveries = [r for r in data["recovery_options"] if r["title"] == "Increase Resource Capacity"]
    assert len(recoveries) > 0
    assert "Add at least 1 capacity" in recoveries[0]["changes_required"]
    
    # Assert health
    assert data["health"]["grade"] in ("critical", "poor")
    assert any("Infeasibility" in f["name"] or "Feasibility" in f["name"] for f in data["health"]["factors"])


def test_impossible_deadline(client, base_plan):
    plan, headers, base = base_plan
    t1 = post(client, f"{base}/tasks", {
        "name": "T1", "duration_minutes": 120, "earliest_start": "2026-09-16T10:00:00+00:00", "deadline": "2026-09-16T11:00:00+00:00"
    }, headers)
    
    response = client.get(f"{base}/analysis", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    issues = [i for i in data["issues"] if i["type"] == "impossible_deadline"]
    assert len(issues) == 1
    assert issues[0]["task_id"] == t1["id"]
    
    recoveries = [r for r in data["recovery_options"] if r["title"] == "Extend Deadline"]
    assert len(recoveries) > 0
    assert "Extend the deadline by at least 60 minutes" in recoveries[0]["changes_required"]


def test_unavailable_specific_resource(client, base_plan):
    plan, headers, base = base_plan
    # Create an inactive resource
    r1 = post(client, f"{base}/resources", {"name": "Senior", "resource_type": "developer", "capacity": 1, "active": False}, headers)
    t1 = post(client, f"{base}/tasks", {"name": "T1", "duration_minutes": 60}, headers)
    post(client, f"{base}/tasks/{t1['id']}/requirements", {"resource_type": "developer", "quantity": 1, "required_resource_id": r1["id"]}, headers)
    
    response = client.get(f"{base}/analysis", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    issues = [i for i in data["issues"] if i["type"] == "specific_resource_unavailable"]
    assert len(issues) == 1
    
    recoveries = [r for r in data["recovery_options"] if r["title"] == "Activate Specific Resource"]
    assert len(recoveries) > 0


def test_feasible_plan_risks_bottlenecks_health(client, application, db_engine, base_plan):
    plan, headers, base = base_plan
    
    # We need a solved run. Since we reuse solver, let's call the solver endpoint on a valid simple plan.
    r1 = post(client, f"{base}/resources", {"name": "Dev", "resource_type": "dev", "capacity": 1}, headers)
    t1 = post(client, f"{base}/tasks", {"name": "T1", "duration_minutes": 60, "deadline": "2026-09-16T10:10:00+00:00"}, headers)
    post(client, f"{base}/tasks/{t1['id']}/requirements", {"resource_type": "dev", "quantity": 1}, headers)
    t2 = post(client, f"{base}/tasks", {"name": "T2", "duration_minutes": 120}, headers)
    post(client, f"{base}/tasks/{t2['id']}/requirements", {"resource_type": "dev", "quantity": 1}, headers)
    t3 = post(client, f"{base}/tasks", {"name": "T3", "duration_minutes": 60}, headers)
    post(client, f"{base}/tasks/{t3['id']}/requirements", {"resource_type": "dev", "quantity": 1}, headers)
    
    # Add a chain to make t1 a bottleneck
    post(client, f"{base}/dependencies", {"before_task_id": t1["id"], "after_task_id": t2["id"]}, headers)
    post(client, f"{base}/dependencies", {"before_task_id": t1["id"], "after_task_id": t3["id"]}, headers)
    
    # We need an additional task so t1 has 3 successors, satisfying the >2 threshold
    t4 = post(client, f"{base}/tasks", {"name": "T4", "duration_minutes": 60}, headers)
    post(client, f"{base}/dependencies", {"before_task_id": t1["id"], "after_task_id": t4["id"]}, headers)
    
    # Call solver
    solve_resp = client.post(f"{base}/solve", headers=headers)
    assert solve_resp.status_code == 200
    
    response = client.get(f"{base}/analysis", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] in ("optimal", "feasible")
    
    # Low slack risk for T1
    slack_risks = [r for r in data["risks"] if "deadline slack" in r["message"]]
    assert len(slack_risks) >= 1
    
    # Bottleneck for dependency
    task_bottlenecks = [b for b in data["bottlenecks"] if b["type"] == "task" and b["task_id"] == t1["id"]]
    assert len(task_bottlenecks) == 1
    assert "dependency" in task_bottlenecks[0]["reason"].lower()
    
    # High utilization bottleneck for Dev
    res_bottlenecks = [b for b in data["bottlenecks"] if b["type"] == "resource" and b["resource_id"] == r1["id"]]
    assert len(res_bottlenecks) == 1
    
    # Health score deterministic
    assert "score" in data["health"]
    assert 0 <= data["health"]["score"] <= 100
    assert len(data["health"]["factors"]) >= 2

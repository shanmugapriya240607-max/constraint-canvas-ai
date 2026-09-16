"""Planning API validation, ownership, relationships, and persistence regression tests."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ConstraintRule, Plan, Resource, ResourceAvailability, Task, TaskDependency, TaskRequirement, User,
)
from app.schemas.planning import ConstraintRuleCreate

START = "2026-09-16T09:00:00+05:30"
END = "2026-09-16T18:00:00+05:30"
PLAN = {"name": "  College Fest Website  ", "planning_start": START, "planning_end": END}
RESOURCE = {"name": "Ravi", "resource_type": "developer", "capacity": 1}
TASK = {"name": "Development", "duration_value": 3, "duration_unit": "hours", "priority": "high"}
WINDOW = {"available_from": START, "available_until": "2026-09-16T13:00:00+05:30"}
RULE = {"constraint_type": "preferred_time", "hardness": "soft", "parameters": {"before": "15:00"}}


def post(client, url, payload, headers):
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code == 201, response.text
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
def plan(client, actors):
    return post(client, "/api/plans", PLAN, actors[0])


@pytest.fixture
def world(client, actors, plan):
    base = f"/api/plans/{plan['id']}"
    resource = post(client, base + "/resources", RESOURCE, actors[0])
    availability = post(client, base + f"/resources/{resource['id']}/availability", WINDOW, actors[0])
    task = post(client, base + "/tasks", TASK, actors[0])
    other = post(client, base + "/tasks", {"name":"Testing", "duration_minutes":90}, actors[0])
    requirement = post(client, base + f"/tasks/{task['id']}/requirements", {
        "resource_type":"developer", "quantity":1, "required_resource_id":resource["id"],
    }, actors[0])
    dependency = post(client, base + "/dependencies", {"before_task_id":task["id"], "after_task_id":other["id"]}, actors[0])
    rule = post(client, base + "/constraints", RULE, actors[0])
    return dict(plan=plan, resource=resource, availability=availability, task=task, other=other,
                requirement=requirement, dependency=dependency, rule=rule, base=base)


def test_plan_creation_listing_and_owner(client, actors, plan):
    assert plan["name"] == "College Fest Website"
    assert plan["status"] == "draft"
    assert plan["planning_start"] == "2026-09-16T03:30:00Z"
    assert client.get("/api/plans", headers=actors[0]).json() == [plan]
    assert client.get("/api/plans", headers=actors[1]).json() == []
    assert client.get(f"/api/plans/{plan['id']}", headers=actors[0]).json() == plan


@pytest.mark.parametrize("changes", [
    {"planning_end":START}, {"planning_end":"2026-09-16T08:00:00+05:30"},
    {"planning_start":"2026-09-16T09:00:00"}, {"name":"   "}, {"user_id":999}, {"status":"solved"},
])
def test_invalid_plan_creation(client, actors, changes):
    assert client.post("/api/plans", json={**PLAN, **changes}, headers=actors[0]).status_code == 422


def test_plan_patch_validates_merged_window(client, actors, plan):
    base = f"/api/plans/{plan['id']}"
    response = client.patch(base, json={"name":" Revised ", "description":"expo", "status":"ready"}, headers=actors[0])
    assert response.status_code == 200
    assert response.json()["name"] == "Revised"
    assert response.json()["updated_at"] >= plan["updated_at"]
    assert client.patch(base, json={"planning_start":END}, headers=actors[0]).status_code == 422
    assert client.patch(base, json={"name":None}, headers=actors[0]).status_code == 422
    assert client.patch(base, json={"description":None}, headers=actors[0]).json()["description"] is None
    assert client.get(base, headers=actors[0]).json()["planning_start"] == plan["planning_start"]


@pytest.mark.parametrize("changes", [
    {"capacity":0}, {"capacity":-2}, {"capacity":1.5}, {"capacity":True},
    {"resource_type":" "}, {"cost_per_hour":-1}, {"name":" "},
])
def test_invalid_resource(client, actors, plan, changes):
    assert client.post(f"/api/plans/{plan['id']}/resources", json={**RESOURCE, **changes}, headers=actors[0]).status_code == 422


def test_resource_duplicate_names_and_updates(client, actors, plan):
    base = f"/api/plans/{plan['id']}/resources"
    first = post(client, base, RESOURCE, actors[0])
    assert client.post(base, json={**RESOURCE, "name":" ravi "}, headers=actors[0]).status_code == 409
    second = post(client, base, {**RESOURCE, "name":"Priya"}, actors[0])
    assert client.patch(f"{base}/{second['id']}", json={"name":"RAVI"}, headers=actors[0]).status_code == 409
    response = client.patch(f"{base}/{first['id']}", json={"capacity":2,"cost_per_hour":"12.50","active":False}, headers=actors[0])
    assert response.status_code == 200
    assert Decimal(response.json()["cost_per_hour"]) == Decimal("12.50")
    assert response.json()["active"] is False
    assert len(client.get(base, headers=actors[0]).json()) == 2
    assert "name_key" not in response.json()
    other_plan = post(client, "/api/plans", PLAN, actors[0])
    post(client, f"/api/plans/{other_plan['id']}/resources", RESOURCE, actors[0])


def test_availability_create_list_patch_delete(client, actors, plan):
    resource = post(client, f"/api/plans/{plan['id']}/resources", RESOURCE, actors[0])
    base = f"/api/plans/{plan['id']}/resources/{resource['id']}/availability"
    first = post(client, base, WINDOW, actors[0])
    second = post(client, base, {"available_from":"2026-09-16T14:00:00+05:30", "available_until":END}, actors[0])
    assert len(client.get(base, headers=actors[0]).json()) == 2
    assert client.patch(f"{base}/{first['id']}", json={"available_until":START}, headers=actors[0]).status_code == 422
    assert client.post(base, json={"available_from":END,"available_until":START}, headers=actors[0]).status_code == 422
    assert client.patch(f"{base}/{second['id']}", json={"available_until":"2026-09-16T17:00:00+05:30"}, headers=actors[0]).status_code == 200
    response = client.delete(f"{base}/{first['id']}", headers=actors[0])
    assert response.status_code == 204 and not response.content
    assert len(client.get(base, headers=actors[0]).json()) == 1


@pytest.mark.parametrize("duration,expected", [
    ({"duration_value":2,"duration_unit":"hours"},120),
    ({"duration_value":30,"duration_unit":"minutes"},30),
    ({"duration_value":1800,"duration_unit":"seconds"},30),
    ({"duration_value":1,"duration_unit":"seconds"},1),
    ({"duration_value":61,"duration_unit":"seconds"},2),
    ({"duration_value":"1.01","duration_unit":"hours"},61),
    ({"duration_value":"0.01","duration_unit":"minutes"},1),
    ({"duration_minutes":45},45),
    ({"duration_value":"60.000000001","duration_unit":"seconds"},2),
    ({"duration_value":60,"duration_unit":"seconds"},1),
])
def test_duration_normalization(client, actors, plan, duration, expected):
    task = post(client, f"/api/plans/{plan['id']}/tasks", {"name":"Task", **duration}, actors[0])
    assert task["duration_minutes"] == expected
    assert "duration_value" not in task and "duration_unit" not in task


@pytest.mark.parametrize("payload", [
    {"duration_value":2}, {"duration_unit":"hours"}, {"duration_value":-1,"duration_unit":"hours"},
    {"duration_minutes":0}, {"duration_minutes":2.5}, {"duration_minutes":True},
    {"duration_value":2,"duration_unit":"days"},
    {"duration_value":2,"duration_unit":"hours","duration_minutes":120},
    {"duration_minutes":60,"priority":"urgent"},
    {"duration_minutes":60,"earliest_start":END,"deadline":START},
    {"duration_minutes":60,"deadline":"2026-09-16T16:00:00"},
])
def test_invalid_task(client, actors, plan, payload):
    response = client.post(f"/api/plans/{plan['id']}/tasks", json={"name":"Task",**payload}, headers=actors[0])
    assert response.status_code == 422


def test_task_update_merged_times_and_duration(client, actors, plan):
    base = f"/api/plans/{plan['id']}/tasks"
    task = post(client, base, {**TASK, "earliest_start":START,"deadline":END}, actors[0])
    url = f"{base}/{task['id']}"
    response = client.patch(url, json={"duration_value":1800,"duration_unit":"seconds", "priority":"critical"}, headers=actors[0])
    assert response.status_code == 200 and response.json()["duration_minutes"] == 30
    assert client.patch(url, json={"duration_value":2}, headers=actors[0]).status_code == 422
    assert client.patch(url, json={"deadline":START}, headers=actors[0]).status_code == 422
    assert client.patch(url, json={"duration_minutes":None}, headers=actors[0]).status_code == 422
    assert client.patch(url, json={"deadline":None,"earliest_start":None}, headers=actors[0]).json()["deadline"] is None
    assert client.get(url, headers=actors[0]).status_code == 200
    assert len(client.get(base, headers=actors[0]).json()) == 1


def test_requirements_validation_and_resource_conflicts(client, actors, world):
    base = world["base"]
    resource_id, task_id = world["resource"]["id"], world["task"]["id"]
    requirements = f"{base}/tasks/{task_id}/requirements"
    generic = post(client, requirements, {"resource_type":" developer ","quantity":2}, actors[0])
    assert generic["required_resource_id"] is None
    assert client.post(requirements, json={"resource_type":"developer","quantity":0}, headers=actors[0]).status_code == 422
    assert client.post(requirements, json={"resource_type":"vehicle","quantity":1,"required_resource_id":resource_id}, headers=actors[0]).status_code == 400
    second_plan = post(client, "/api/plans", PLAN, actors[0])
    other_resource = post(client, f"/api/plans/{second_plan['id']}/resources", RESOURCE, actors[0])
    assert client.post(requirements, json={"resource_type":"developer","quantity":1,"required_resource_id":other_resource["id"]}, headers=actors[0]).status_code == 404
    url = f"{base}/resources/{resource_id}"
    assert client.patch(url, json={"resource_type":"vehicle"}, headers=actors[0]).status_code == 409
    assert client.delete(url, headers=actors[0]).status_code == 409
    assert len(client.get(requirements, headers=actors[0]).json()) == 2
    assert client.delete(f"{requirements}/{world['requirement']['id']}", headers=actors[0]).status_code == 204
    assert client.delete(url, headers=actors[0]).status_code == 204
    assert client.get(url + "/availability", headers=actors[0]).status_code == 404


def test_dependencies_self_duplicate_cycle_and_cross_plan(client, actors, world):
    base = world["base"]
    a, b = world["task"]["id"], world["other"]["id"]
    c = post(client, base + "/tasks", {"name":"C","duration_minutes":1}, actors[0])["id"]
    url = base + "/dependencies"
    assert client.post(url, json={"before_task_id":a,"after_task_id":a}, headers=actors[0]).status_code == 400
    assert client.post(url, json={"before_task_id":a,"after_task_id":b}, headers=actors[0]).status_code == 409
    post(client, url, {"before_task_id":b,"after_task_id":c}, actors[0])
    assert client.post(url, json={"before_task_id":c,"after_task_id":a}, headers=actors[0]).status_code == 400
    other_plan = post(client,"/api/plans",PLAN,actors[0])
    outsider = post(client,f"/api/plans/{other_plan['id']}/tasks",TASK,actors[0])["id"]
    assert client.post(url,json={"before_task_id":a,"after_task_id":outsider},headers=actors[0]).status_code == 404
    assert len(client.get(url,headers=actors[0]).json()) == 2
    assert client.delete(f"{url}/{world['dependency']['id']}",headers=actors[0]).status_code == 204


def test_concurrent_dependencies_cannot_create_cycle(client, actors, plan):
    base = f"/api/plans/{plan['id']}"
    a = post(client,base+"/tasks",{"name":"A","duration_minutes":1},actors[0])["id"]
    b = post(client,base+"/tasks",{"name":"B","duration_minutes":1},actors[0])["id"]
    def add(pair):
        return client.post(base+"/dependencies",json={"before_task_id":pair[0],"after_task_id":pair[1]},headers=actors[0]).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(add, [(a,b),(b,a)])) == [201,400]


def test_constraint_defaults_and_patch(client, actors, plan):
    url = f"/api/plans/{plan['id']}/constraints"
    hard = post(client,url,{"constraint_type":"deadline"},actors[0])
    assert hard["weight"] is None and hard["source"] == "manual"
    soft = post(client,url,RULE,actors[0])
    assert soft["weight"] == 1
    weighted = post(client,url,{**RULE,"weight":2.5},actors[0])
    assert weighted["weight"] == 2.5
    response = client.patch(f"{url}/{hard['id']}",json={"hardness":"soft"},headers=actors[0])
    assert response.status_code == 200 and response.json()["weight"] == 1
    assert client.patch(f"{url}/{soft['id']}",json={"weight":None},headers=actors[0]).status_code == 422
    assert client.patch(f"{url}/{soft['id']}",json={"hardness":"hard","weight":None,"enabled":False},headers=actors[0]).status_code == 200
    assert len(client.get(url,headers=actors[0]).json()) == 3
    assert client.delete(f"{url}/{weighted['id']}",headers=actors[0]).status_code == 204


@pytest.mark.parametrize("changes", [
    {"hardness":"unknown"}, {"source":"user"}, {"constraint_type":"execute"},
    {"weight":0}, {"weight":-1}, {"weight":None}, {"parameters":[]},
    {"parameters":{"large":"x"*65537}},
])
def test_invalid_constraint(client, actors, plan, changes):
    assert client.post(f"/api/plans/{plan['id']}/constraints",json={**RULE,**changes},headers=actors[0]).status_code == 422


def test_custom_rules_are_inert_and_nonfinite_json_rejected(client, actors, plan):
    url = f"/api/plans/{plan['id']}/constraints"
    parameters = {"expression":"__import__('os').system('should never run')", "nested":[1, True, None, {"x":"value"}]}
    saved = post(client,url,{"constraint_type":"custom","parameters":parameters},actors[0])
    assert saved["parameters"] == parameters
    response = client.post(url,content='{"constraint_type":"custom","parameters":{"x":NaN}}',headers={**actors[0],"Content-Type":"application/json"})
    assert response.status_code == 422
    with pytest.raises(ValidationError):
        ConstraintRuleCreate(constraint_type="custom", parameters={"object":object()})


def test_full_plan_is_complete_and_has_no_solver_data(client, actors, world):
    full = client.get(world["base"]+"/full",headers=actors[0])
    assert full.status_code == 200
    data = full.json()
    assert set(data) == {"plan","resources","tasks","dependencies","constraints"}
    assert data["plan"]["id"] == world["plan"]["id"]
    assert data["resources"][0]["availability"] == [world["availability"]]
    assert data["tasks"][0]["requirements"] == [world["requirement"]]
    assert data["tasks"][0]["duration_minutes"] == 180
    assert data["dependencies"] == [world["dependency"]]
    assert data["constraints"] == [world["rule"]]
    assert "password_hash" not in full.text and "name_key" not in full.text


# Every declared operation is tested for both anonymous and cross-user access.
OPERATIONS = [
    ("POST","",PLAN),("GET","",None),("GET","/{p}",None),("PATCH","/{p}",{"name":"Changed"}),("DELETE","/{p}",None),
    ("GET","/{p}/full",None),
    ("POST","/{p}/resources",RESOURCE),("GET","/{p}/resources",None),("GET","/{p}/resources/{r}",None),
    ("PATCH","/{p}/resources/{r}",{"name":"Changed"}),("DELETE","/{p}/resources/{r}",None),
    ("POST","/{p}/resources/{r}/availability",WINDOW),("GET","/{p}/resources/{r}/availability",None),
    ("PATCH","/{p}/resources/{r}/availability/{a}",WINDOW),("DELETE","/{p}/resources/{r}/availability/{a}",None),
    ("POST","/{p}/tasks",TASK),("GET","/{p}/tasks",None),("GET","/{p}/tasks/{t}",None),
    ("PATCH","/{p}/tasks/{t}",{"name":"Changed"}),("DELETE","/{p}/tasks/{t}",None),
    ("POST","/{p}/tasks/{t}/requirements",{"resource_type":"developer","quantity":1}),
    ("GET","/{p}/tasks/{t}/requirements",None),("DELETE","/{p}/tasks/{t}/requirements/{q}",None),
    ("POST","/{p}/dependencies",{"before_task_id":1,"after_task_id":2}),
    ("GET","/{p}/dependencies",None),("DELETE","/{p}/dependencies/{d}",None),
    ("POST","/{p}/constraints",RULE),("GET","/{p}/constraints",None),
    ("PATCH","/{p}/constraints/{c}",{"enabled":False}),("DELETE","/{p}/constraints/{c}",None),
]


@pytest.mark.parametrize("method,path,payload",OPERATIONS)
def test_all_planning_operations_require_auth(client, method, path, payload):
    path = "/api/plans" + path.format(p=1,r=1,a=1,t=1,q=1,d=1,c=1)
    assert client.request(method,path,json=payload).status_code == 401


@pytest.mark.parametrize("method,path,payload",[op for op in OPERATIONS if op[1]])
def test_all_nested_operations_block_other_users(client, actors, world, method, path, payload):
    path = "/api/plans" + path.format(p=world["plan"]["id"],r=world["resource"]["id"],a=world["availability"]["id"],
        t=world["task"]["id"],q=world["requirement"]["id"],d=world["dependency"]["id"],c=world["rule"]["id"])
    assert client.request(method,path,json=payload,headers=actors[1]).status_code == 404


@pytest.mark.parametrize("suffix",[
    "/resources/{r}", "/resources/{r}/availability", "/tasks/{t}", "/tasks/{t}/requirements",
])
def test_foreign_child_ids_in_owned_plan_are_hidden(client, actors, world, suffix):
    own = post(client,"/api/plans",PLAN,actors[1])
    path = f"/api/plans/{own['id']}" + suffix.format(r=world["resource"]["id"],t=world["task"]["id"])
    assert client.get(path,headers=actors[1]).status_code == 404


def test_mismatched_nested_child_ids(client, actors, world):
    other = post(client,"/api/plans",PLAN,actors[0])
    base = f"/api/plans/{other['id']}"
    resource = post(client,base+"/resources",RESOURCE,actors[0])
    task = post(client,base+"/tasks",TASK,actors[0])
    paths = [
        f"{base}/resources/{resource['id']}/availability/{world['availability']['id']}",
        f"{base}/tasks/{task['id']}/requirements/{world['requirement']['id']}",
        f"{base}/dependencies/{world['dependency']['id']}", f"{base}/constraints/{world['rule']['id']}",
    ]
    for path in paths:
        assert client.delete(path,headers=actors[0]).status_code == 404


def test_plan_delete_cascades_all_planning_data(client, actors, world, db_engine):
    assert client.delete(world["base"],headers=actors[0]).status_code == 204
    assert client.get(world["base"],headers=actors[0]).status_code == 404
    with Session(db_engine) as db:
        for model in (Plan,Resource,ResourceAvailability,Task,TaskRequirement,TaskDependency,ConstraintRule):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert db.scalar(select(func.count()).select_from(User)) == 2
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []


def test_task_delete_cascades_edges_and_requirements(client, actors, world, db_engine):
    assert client.delete(world["base"]+f"/tasks/{world['task']['id']}",headers=actors[0]).status_code == 204
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(TaskRequirement)) == 0
        assert db.scalar(select(func.count()).select_from(TaskDependency)) == 0
        assert db.scalar(select(func.count()).select_from(Task)) == 1
        assert db.scalar(select(func.count()).select_from(Resource)) == 1


def test_database_rejects_cross_plan_references(client, actors, world, db_engine):
    other = post(client,"/api/plans",PLAN,actors[0])
    task = post(client,f"/api/plans/{other['id']}/tasks",TASK,actors[0])
    with Session(db_engine) as db:
        db.add(TaskDependency(plan_id=world["plan"]["id"],before_task_id=world["task"]["id"],after_task_id=task["id"]))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(TaskRequirement(plan_id=other["id"],task_id=task["id"],resource_type="developer",quantity=1,required_resource_id=world["resource"]["id"]))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_openapi_documents_every_planning_operation(client):
    schema = client.get("/openapi.json").json()
    routes = {path:operations for path,operations in schema["paths"].items() if path.startswith("/api/plans")}
    operations = [operation for path in routes.values() for method,operation in path.items() if method in {"get","post","patch","delete"}]
    assert len(operations) == len(OPERATIONS) == 30
    assert all(operation["security"] == [{"HTTPBearer":[]}] for operation in operations)
    assert client.get("/docs").status_code == 200


def test_concurrent_plan_patches_merge_latest_state(client, actors, plan, application):
    from threading import Barrier
    from app.dependencies.ownership import Database, OwnedPlan, get_writable_plan

    barrier = Barrier(2, timeout=10)

    def synchronize_after_read(plan: OwnedPlan, db: Database):
        # Both requests read the same original plan before either acquires its lock.
        barrier.wait()
        return get_writable_plan(plan, db)

    application.dependency_overrides[get_writable_plan] = synchronize_after_read
    url = f"/api/plans/{plan['id']}"
    try:
        def change(payload):
            return client.patch(url, json=payload, headers=actors[0]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(change, [{"name":"New name"}, {"description":"New description"}])) == [200,200]
    finally:
        application.dependency_overrides.clear()
    stored = client.get(url, headers=actors[0]).json()
    assert stored["name"] == "New name" and stored["description"] == "New description"

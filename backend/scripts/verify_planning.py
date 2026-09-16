"""Run the Phase 3 manual scenario against a local server and inspect its SQLite data.

From backend/: .venv/Scripts/python.exe scripts/verify_planning.py
Start the server from backend/ with the same DATABASE_URL settings on port 8002.
Creates a fresh verification user and plan, preserves all existing records, and writes
examples/college_fest_plan.json without any password, JWT, or secret.
"""
import json
from pathlib import Path
import secrets
import sys
import uuid

import httpx
from sqlalchemy import func, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models import Plan, Resource, ResourceAvailability, Task, TaskDependency, TaskRequirement, ConstraintRule, User
from app.services.security import verify_password

BASE_URL = "http://127.0.0.1:8002"
START, END = "2026-09-16T09:00:00+05:30", "2026-09-16T18:00:00+05:30"


def main():
    email = f"planning-expo-{uuid.uuid4().hex[:10]}@example.com"
    password = secrets.token_urlsafe(24)
    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        for path in ("/", "/api/health", "/docs"):
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
        assert client.get("/api/health").json()["database"] == "connected"
        registration = client.post("/api/auth/register", json={"name":"Expo Verification", "email":email, "password":password})
        assert registration.status_code == 201
        user_id = registration.json()["id"]
        login = client.post("/api/auth/login", json={"email":email, "password":password})
        assert login.status_code == 200
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        assert client.get("/api/auth/me").json()["id"] == user_id

        def create(path, payload):
            response = client.post(path, json=payload)
            assert response.status_code == 201, (path, response.status_code, response.text)
            return response.json()

        plan = create("/api/plans", {"name":"College Fest Website", "planning_start":START, "planning_end":END})
        base = f"/api/plans/{plan['id']}"
        resources = [create(base+"/resources", {"name":name,"resource_type":"developer","capacity":capacity})
                     for name,capacity in [("Ravi",1),("Priya",1),("Developer Pool",2)]]
        for resource, until in zip(resources, ["2026-09-16T13:00:00+05:30", END]):
            create(base+f"/resources/{resource['id']}/availability", {"available_from":START,"available_until":until})
        development = create(base+"/tasks", {"name":"Development","duration_value":3,"duration_unit":"hours","priority":"high"})
        testing = create(base+"/tasks", {"name":"Testing","duration_value":90,"duration_unit":"minutes","priority":"critical","deadline":"2026-09-16T16:00:00+05:30"})
        documentation = create(base+"/tasks", {"name":"Documentation","duration_minutes":45})
        create(base+f"/tasks/{development['id']}/requirements", {"resource_type":"developer","quantity":2})
        create(base+f"/tasks/{testing['id']}/requirements", {"resource_type":"developer","quantity":1,"required_resource_id":resources[0]["id"]})
        create(base+"/dependencies", {"before_task_id":development["id"],"after_task_id":testing["id"]})
        create(base+"/constraints", {"constraint_type":"preferred_time","hardness":"soft","parameters":{"task_id":testing["id"],"preferred_before":"2026-09-16T15:00:00+05:30"}})
        response = client.get(base+"/full")
        assert response.status_code == 200
        full = response.json()
        assert [task["duration_minutes"] for task in full["tasks"]] == [180,90,45]
        assert [len(resource["availability"]) for resource in full["resources"]] == [1,1,0]
        assert [len(task["requirements"]) for task in full["tasks"]] == [1,1,0]
        assert full["tasks"][1]["requirements"][0]["required_resource_id"] == resources[0]["id"]
        assert full["dependencies"][0]["before_task_id"] == development["id"]
        assert full["dependencies"][0]["after_task_id"] == testing["id"]
        assert full["constraints"][0]["weight"] == 1
        assert full["plan"]["status"] == "draft"
        schema = client.get("/openapi.json").json()
        assert base.replace(str(plan["id"]), "{plan_id}")+"/full" in schema["paths"]

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.email == email and verify_password(password, user.password_hash)
        assert user.password_hash.startswith("$argon2id$")
        assert db.get(Plan, plan["id"]).user_id == user_id
        for model,count in [(Resource,3),(Task,3),(TaskRequirement,2),(TaskDependency,1),(ConstraintRule,1)]:
            assert db.scalar(select(func.count()).select_from(model).where(model.plan_id == plan["id"])) == count
        assert db.scalar(select(func.count()).select_from(ResourceAvailability).join(Resource).where(Resource.plan_id == plan["id"])) == 2
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []

    output = Path(__file__).resolve().parents[1] / "examples" / "college_fest_plan.json"
    output.write_text(json.dumps(full, indent=2) + "\n", encoding="utf-8")
    print("Register 201; login 200; me 200; root/health/docs 200; full plan 200")
    print("Database ownership, foreign keys, canonical minutes, and Argon2id verified")
    print(f"Full response saved to {output}")
    print(json.dumps(full, indent=2))


if __name__ == "__main__":
    main()

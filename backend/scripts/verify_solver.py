"""Phase 4 live checks. Start this backend on localhost:8003 with identical DB settings.
Creates separate demo plans, never changes existing plans, never prints credentials.
"""
import json
from pathlib import Path
import secrets
import sys
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models import Plan, SolverRun


def main():
    output = Path(__file__).resolve().parents[1]/"examples"
    with httpx.Client(base_url="http://127.0.0.1:8003",timeout=40) as client:
        for path in ("/","/api/health","/docs"):
            assert client.get(path).status_code == 200
        headers = []
        for role in ("owner","other"):
            email,password = f"solver-{role}-{uuid.uuid4().hex[:8]}@example.com",secrets.token_urlsafe(24)
            assert client.post("/api/auth/register",json={"name":"Solver Demo","email":email,"password":password}).status_code == 201
            login = client.post("/api/auth/login",json={"email":email,"password":password})
            assert login.status_code == 200
            headers.append({"Authorization":"Bearer "+login.json()["access_token"]})
            assert client.get("/api/auth/me",headers=headers[-1]).status_code == 200

        def create(path,payload):
            response = client.post(path,json=payload,headers=headers[0])
            assert response.status_code == 201,(path,response.status_code,response.text)
            return response.json()

        def new_plan(name):
            return create("/api/plans",{"name":name,"planning_start":"2026-09-16T09:00:00+05:30","planning_end":"2026-09-16T18:00:00+05:30"})

        def expo(name,ravi_until):
            plan = new_plan(name)
            base = f"/api/plans/{plan['id']}"
            resources = [create(base+"/resources",{"name":name,"resource_type":"developer","capacity":capacity})
                for name,capacity in [("Ravi",1),("Priya",1),("Developer Pool",2)]]
            for res,until in zip(resources,[ravi_until,"18:00"]):
                create(base+f"/resources/{res['id']}/availability",{"available_from":"2026-09-16T09:00:00+05:30","available_until":f"2026-09-16T{until}:00+05:30"})
            development = create(base+"/tasks",{"name":"Development","duration_minutes":180,"priority":"high"})
            testing = create(base+"/tasks",{"name":"Testing","duration_minutes":90,"priority":"critical","deadline":"2026-09-16T16:00:00+05:30"})
            create(base+"/tasks",{"name":"Documentation","duration_minutes":45,"priority":"medium"})
            create(base+f"/tasks/{development['id']}/requirements",{"resource_type":"developer","quantity":2})
            create(base+f"/tasks/{testing['id']}/requirements",{"resource_type":"developer","quantity":1,"required_resource_id":resources[0]["id"]})
            create(base+"/dependencies",{"before_task_id":development["id"],"after_task_id":testing["id"]})
            create(base+"/constraints",{"constraint_type":"preferred_time","hardness":"soft","parameters":{"task_id":testing["id"],"preferred_before":"2026-09-16T15:00:00+05:30"}})
            return plan,resources

        original,_ = expo("College Fest Website — original 13:00 cutoff","13:00")
        original_result = client.post(f"/api/plans/{original['id']}/solve",headers=headers[0]).json()
        assert original_result["status"] == "infeasible" and original_result["schedule"] == []
        feasible,resources = expo("College Fest Website — feasible variant (Ravi until 13:30)","13:30")
        base = f"/api/plans/{feasible['id']}"
        solved = client.post(base+"/solve",json={"max_solve_seconds":10},headers=headers[0])
        assert solved.status_code == 200,solved.text
        result = solved.json()
        assert result["status"] in ("optimal","feasible")
        entries = {entry["task_name"]:entry for entry in result["schedule"]}
        assert entries["Development"]["end_offset_minutes"] <= entries["Testing"]["start_offset_minutes"]
        testing = entries["Testing"]
        assert [(a["resource_id"],a["units"]) for a in testing["assigned_resources"]] == [(resources[0]["id"],1)]
        assert testing["end_offset_minutes"] <= 270 and testing["end_offset_minutes"] <= 420
        assert sum(a["units"] for a in entries["Development"]["assigned_resources"]) == 2
        capacities = {r["id"]:r["capacity"] for r in resources}
        loads = {rid:[0]*540 for rid in capacities}
        for entry in result["schedule"]:
            assert 0 <= entry["start_offset_minutes"] < entry["end_offset_minutes"] <= 540
            assert entry["end_offset_minutes"]-entry["start_offset_minutes"] == entry["duration_minutes"]
            for assignment in entry["assigned_resources"]:
                if assignment["resource_id"] == resources[0]["id"]:
                    assert entry["end_offset_minutes"] <= 270
                for minute in range(entry["start_offset_minutes"],entry["end_offset_minutes"]):
                    loads[assignment["resource_id"]][minute] += assignment["units"]
        assert all(max(loads[rid]) <= capacity for rid,capacity in capacities.items())
        assert client.get(base,headers=headers[0]).json()["status"] == "solved"
        assert client.get(base+"/runs",headers=headers[0]).json()[0]["id"] == result["run_id"]
        assert client.get(base+f"/runs/{result['run_id']}",headers=headers[0]).json()["result"] == result
        assert client.post(base+"/solve",headers=headers[1]).status_code == 404
        assert client.get(base+"/runs",headers=headers[1]).status_code == 404
        assert client.get(base+f"/runs/{result['run_id']}",headers=headers[1]).status_code == 404
        assert client.post(base+"/solve").status_code == 401

        impossible = new_plan("Insufficient capacity — three units required, two available")
        ibase = f"/api/plans/{impossible['id']}"
        create(ibase+"/resources",{"name":"Two developers","resource_type":"developer","capacity":2})
        work = create(ibase+"/tasks",{"name":"Three-unit task","duration_minutes":60})
        create(ibase+f"/tasks/{work['id']}/requirements",{"resource_type":"developer","quantity":3})
        failed_response = client.post(ibase+"/solve",headers=headers[0])
        assert failed_response.status_code == 200
        failed = failed_response.json()
        assert failed["status"] == "infeasible" and failed["schedule"] == []
        assert client.get(ibase,headers=headers[0]).json()["status"] == "infeasible"
        schema = client.get("/openapi.json").json()
        assert all(path in schema["paths"] for path in ("/api/plans/{plan_id}/solve","/api/plans/{plan_id}/runs","/api/plans/{plan_id}/runs/{run_id}"))
        with SessionLocal() as db:
            for response in (original_result,result,failed):
                stored = db.get(SolverRun,response["run_id"])
                assert stored.result == response and stored.input_snapshot["tasks"]
            assert db.get(Plan,feasible["id"]).status == "solved"
            assert db.get(Plan,impossible["id"]).status == "infeasible"
        for name,response in [("solver_feasible.json",result),("solver_infeasible.json",failed),("solver_original_expo.json",original_result)]:
            (output/name).write_text(json.dumps(response,indent=2)+"\n",encoding="utf-8")
        print("Auth, Swagger, ownership, hard constraints, capacity, statuses, and persisted history verified")
        print("Original 13:00 scenario: infeasible; separate 13:30 variant: " + result["status"])
        print(json.dumps(result,indent=2))
        print("Capacity shortage: " + json.dumps(failed))


if __name__ == "__main__":
    main()

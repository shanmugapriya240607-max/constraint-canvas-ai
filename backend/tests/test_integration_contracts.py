"""Contracts exercised by the merged frontend; Gemini extraction is mocked."""
import json
from unittest.mock import Mock

from app.services.ai.gemini_client import get_gemini_client
from tests.test_ai_parser import actors, example, TEXT


def test_frontend_route_inventory(client):
    paths = client.get("/openapi.json").json()["paths"]
    required = {
        "/api/auth/register": "post", "/api/auth/login": "post", "/api/auth/me": "get",
        "/api/plans": "post", "/api/plans/{plan_id}/full": "get",
        "/api/ai/parse-plan": "post", "/api/ai/confirm-plan": "post",
        "/api/plans/{plan_id}/solve": "post", "/api/plans/{plan_id}/analysis": "get",
        "/api/plans/{plan_id}/explanation": "get", "/api/plans/{plan_id}/what-if": "post",
        "/api/plans/{plan_id}/compare-scenarios": "post", "/api/memory/consent": "put",
        "/api/memory": "post", "/api/memory/habits": "get", "/api/memory/habits/detect": "post",
        "/api/plans/{plan_id}/context": "get", "/api/plans/{plan_id}/context/apply": "post",
    }
    for path, method in required.items():
        assert method in paths[path], (path, method)


def test_preview_confirm_solve_analysis_explanation_and_scenarios(client, application, actors):
    provider = Mock(extract=Mock(return_value=json.dumps(example())))
    application.dependency_overrides[get_gemini_client] = lambda: provider
    owner = actors[0]
    preview = client.post("/api/ai/parse-plan", headers=owner, json={"text": TEXT})
    assert preview.status_code == 200, preview.text
    assert client.get("/api/plans", headers=owner).json() == []
    draft = preview.json()["draft"]
    answers = [{"field": "plan." + key, "value": value} for key, value in draft["plan"].items() if value is not None]
    answers += [{"field": field, "value": draft[field]} for field in ("tasks", "resources", "requirements", "dependencies", "constraints")]
    confirmed = client.post("/api/ai/confirm-plan", headers=owner, json={"confirmed": True, "draft": draft, "answers": answers})
    assert confirmed.status_code == 201, confirmed.text
    base = f"/api/plans/{confirmed.json()['plan_id']}"
    full = client.get(base + "/full", headers=owner).json()
    assert set(full) == {"plan", "resources", "tasks", "dependencies", "constraints"}
    solved = client.post(base + "/solve", headers=owner)
    assert solved.status_code == 200, solved.text
    assert solved.json()["status"] == "optimal"
    runs = client.get(base + "/runs", headers=owner).json()
    assert runs[0]["solver_status"] == "optimal"
    detail = client.get(base + f"/runs/{runs[0]['id']}", headers=owner).json()
    assert len(detail["result"]["schedule"]) == 2
    analysis = client.get(base + "/analysis", headers=owner).json()
    assert analysis["status"] == "optimal" and isinstance(analysis["health"]["score"], int)
    explanation = client.get(base + "/explanation", headers=owner).json()
    assert explanation["run_id"] == runs[0]["id"] and explanation["tasks"]
    full = client.get(base + "/full", headers=owner).json()
    task = full["tasks"][0]
    changes = [{"type": "priority_change", "task_id": task["id"], "priority": "high"}]
    simulated = client.post(base + "/what-if", headers=owner, json={"changes": changes})
    assert simulated.status_code == 200, simulated.text
    assert "health_score" in simulated.json()["scenario"]
    assert "health_change" in simulated.json()["impact"]
    assert "schedule" in simulated.json()
    comparison = client.post(base + "/compare-scenarios", headers=owner, json={"scenarios": [{"name": "A", "changes": changes}, {"name": "B", "changes": []}]})
    assert comparison.status_code == 200, comparison.text
    assert len(comparison.json()["scenarios"]) == 2
    assert "issues_count" in comparison.json()["scenarios"][0]
    assert client.get(base + "/full", headers=owner).json() == full
    assert len(client.get(base + "/runs", headers=owner).json()) == 1
    provider.extract.assert_called_once_with(TEXT)


def test_memory_habit_route_and_context_shapes(client, actors):
    owner = actors[0]
    assert client.get("/api/memory/habits", headers=owner).json() == []
    consent = client.put("/api/memory/consent", headers=owner, json={"enabled": True})
    assert consent.json() == {"memory_enabled": True}
    memory = client.post("/api/memory", headers=owner, json={"memory_type": "working_hours", "key": "Hours", "value": {"text": "Morning"}, "source": "explicit"})
    assert memory.status_code == 200, memory.text
    assert memory.json()["value"] == {"text": "Morning"}
    plan = client.post("/api/plans", headers=owner, json=example()["plan"]).json()
    base = f"/api/plans/{plan['id']}"
    context = client.get(base + "/context", headers=owner)
    assert context.status_code == 200, context.text
    assert context.json()["requires_confirmation"] is True
    assert context.json()["relevant_context"][0]["memory_id"] == memory.json()["id"]
    applied = client.post(base + "/context/apply", headers=owner, json={"memory_ids": [memory.json()["id"]]})
    assert applied.status_code == 422  # Free-text hours cannot be turned into a rule implicitly.
    assert client.get(base + "/full", headers=owner).json()["constraints"] == []

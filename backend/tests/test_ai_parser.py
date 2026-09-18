"""B5 contract tests use fake extraction or MockTransport, never the real provider."""
import copy
import json
from decimal import Decimal
from unittest.mock import Mock
import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import User, Plan, Task, Resource, ConstraintRule
from app.schemas.ai_parser import PlanningDraft, CustomField, ConstraintDraft
from app.services.ai.dynamic_schema import build_dynamic_model, validate_custom_fields
from app.services.ai.gemini_client import GeminiClient, GeminiSettings, get_gemini_client
from app.services.ai.planning_parser import inspect_draft, parse_plan
from app.services.ai.constraint_mapping import map_constraint

START = "2026-09-17T09:00:00+05:30"
END = "2026-09-17T18:00:00+05:30"
DEADLINE = "2026-09-17T17:00:00+05:30"
TEXT = (
    "Website launch on 2026-09-17T09:00:00+05:30 through 2026-09-17T18:00:00+05:30. "
    "We have 3 developers. Ravi is a developer with capacity 1, separate from the 3 developers. "
    "Development takes 3 hours, has medium priority and needs 2 developers. "
    "Testing takes 90 minutes and must happen after Development. "
    "Ravi must perform Testing, which needs 1 developer. "
    "Testing is critical and must finish by 2026-09-17T17:00:00+05:30."
)


def example(evidence=True):
    data = {
        "plan": {"name": "Website launch", "planning_start": START, "planning_end": END},
        "resources": [
            {"client_id": "pool", "name": "developers", "resource_type": "developer", "capacity": 3},
            {"client_id": "ravi", "name": "Ravi", "resource_type": "developer", "capacity": 1},
        ],
        "tasks": [
            {"client_id": "dev", "name": "Development", "duration_value": 3, "duration_unit": "hours", "priority": "medium"},
            {"client_id": "test", "name": "Testing", "duration_value": 90, "duration_unit": "minutes", "priority": "critical", "deadline": DEADLINE},
        ],
        "requirements": [
            {"task_id": "dev", "resource_type": "developer", "quantity": 2},
            {"task_id": "test", "resource_type": "developer", "quantity": 1, "required_resource_id": "ravi"},
        ],
        "dependencies": [{"before_task_id": "dev", "after_task_id": "test"}],
    }
    if evidence:
        fields = ["plan." + key for key in data["plan"]]
        for collection in ("resources", "tasks"):
            fields.extend(f"{collection}.{i}.{key}" for i, item in enumerate(data[collection]) for key in item if key != "client_id")
        fields.extend(f"{collection}.{i}" for collection in ("requirements", "dependencies") for i in range(len(data[collection])))
        data["evidence"] = [{"field": field, "quote": TEXT} for field in fields]
    return data


@pytest.fixture
def actors(client, application, db_engine):
    with Session(db_engine) as db:
        users = [User(name=f"AI User {i}", email=f"ai{i}@example.com", password_hash="unused") for i in range(2)]
        db.add_all(users)
        db.commit()
        ids = [user.id for user in users]
    return [{"Authorization": "Bearer " + application.state.token_service.issue(user_id)} for user_id in ids]


@pytest.fixture
def provider(application):
    mock = Mock()
    mock.extract.return_value = json.dumps(example())
    application.dependency_overrides[get_gemini_client] = lambda: mock
    yield mock
    application.dependency_overrides.pop(get_gemini_client, None)


def parse(client, actors, **kwargs):
    return client.post("/api/ai/parse-plan", json={"text": TEXT, **kwargs}, headers=actors[0])


def confirm(client, actors, draft=None, **kwargs):
    return client.post("/api/ai/confirm-plan", json={
        "confirmed": True, "draft": draft or example(), **kwargs,
    }, headers=actors[0])


def test_english_extraction_and_preview_does_not_persist(client, actors, provider, db_engine):
    response = parse(client, actors)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ready", result
    draft = result["draft"]
    assert draft["resources"][0]["capacity"] == 3
    assert draft["tasks"][0]["name"] == "Development"
    assert Decimal(draft["tasks"][0]["duration_value"]) == 3
    assert draft["tasks"][0]["duration_unit"] == "hours"
    assert draft["tasks"][1]["priority"] == "critical"
    assert draft["tasks"][1]["deadline"] == "2026-09-17T11:30:00Z"
    assert draft["requirements"][0]["quantity"] == 2
    assert draft["requirements"][1]["required_resource_id"] == "ravi"
    assert draft["dependencies"] == [{"before_task_id": "dev", "after_task_id": "test"}]
    assert result["requires_confirmation"] is True
    provider.extract.assert_called_once_with(TEXT)
    with Session(db_engine) as db:
        for model in (Plan, Resource, Task):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_missing_duration_unit_is_deterministic(client, actors, provider):
    data = example()
    data["tasks"][0]["duration_unit"] = None
    provider.extract.return_value = json.dumps(data)
    result = parse(client, actors).json()
    assert result["status"] == "needs_clarification"
    question = next(q for q in result["questions"] if q["field"] == "tasks.0.duration_unit")
    assert question["allowed_answers"] == ["seconds", "minutes", "hours"]


def test_no_resources_or_durations_are_invented(client, actors, provider):
    provider.extract.return_value = json.dumps({"plan": {}, "tasks": [{"client_id": "test", "name": "Testing"}]})
    result = parse(client, actors, text="Plan Testing tomorrow").json()
    assert result["status"] == "needs_clarification"
    assert result["draft"]["resources"] == []
    assert result["draft"]["tasks"][0]["duration_value"] is None
    assert result["draft"]["tasks"][0]["priority"] is None
    assert result["draft"]["plan"]["planning_start"] is None


@pytest.mark.parametrize("raw", [
    "not JSON", "{}", '{"plan":{},"tasks":[],"tasks":[]}', '{"plan":{},"schedule":[]}',
    '{"plan":{},"tasks":[{"client_id":"a","duration_value":-1}]}',
    '{"plan":{},"constraints":[{"semantic":"x","operator":"execute"}]}',
])
def test_malformed_or_unsafe_extraction_returns_invalid(client, actors, provider, raw):
    provider.extract.return_value = raw
    result = parse(client, actors)
    assert result.status_code == 200
    assert result.json()["status"] == "invalid"
    assert result.json()["draft"] is None
    assert "Traceback" not in result.text


def test_clock_only_deadline_needs_date_timezone():
    data = example()
    data["tasks"][1].update(deadline=None, deadline_text="5 PM")
    preview = inspect_draft(PlanningDraft.model_validate(data))
    assert preview.status == "needs_clarification"
    assert any(q.field == "tasks.1.deadline" for q in preview.questions)


def test_unsubstantiated_unit_does_not_become_ready():
    data = example()
    raw = json.dumps(data)
    response = parse_plan(Mock(extract=Mock(return_value=raw)), "Testing takes 3.")
    assert response.status == "needs_clarification"
    assert any(q.field == "tasks.1.duration_unit" for q in response.questions)


@pytest.mark.parametrize("type_name,value", [
    ("string", "text"), ("integer", 6), ("float", 6.25), ("boolean", True),
    ("datetime", START), ("time", "17:00:00"),
])
def test_all_dynamic_types(type_name, value):
    field = CustomField(name="custom_value", type=type_name)
    result = validate_custom_fields([field], {"custom_value": value})
    assert "custom_value" in result


@pytest.mark.parametrize("value", [0, 25, 1.5, True, "6", None])
def test_dynamic_integer_rejects_invalid_values(value):
    definition = CustomField(name="max_daily_hours", type="integer", minimum=1, maximum=24)
    with pytest.raises(ValidationError):
        validate_custom_fields([definition], {"max_daily_hours": value})


@pytest.mark.parametrize("value", ["tomorrow", "2026-09-17T09:00:00", 1234])
def test_dynamic_datetime_rejects_ambiguous_or_coerced_values(value):
    with pytest.raises(ValidationError):
        validate_custom_fields([CustomField(name="date", type="datetime")], {"date": value})


@pytest.mark.parametrize("definition", [
    {"name": "bad", "type": "__import__('os')"},
    {"name": "__class__", "type": "string"},
    {"name": "model_dump", "type": "string"},
    {"name": "value", "type": "integer", "minimum": 24, "maximum": 1},
    {"name": "value", "type": "boolean", "minimum": 1},
    {"name": "value", "type": "integer", "minimum": 1.5},
])
def test_dynamic_definitions_reject_unsafe_or_invalid_input(definition):
    with pytest.raises(ValidationError):
        CustomField.model_validate(definition)


def test_dynamic_extra_duplicate_and_required_fields():
    definition = CustomField(name="value", type="integer")
    with pytest.raises(ValueError):
        build_dynamic_model([definition, definition])
    with pytest.raises(ValidationError):
        validate_custom_fields([definition], {})
    with pytest.raises(ValidationError):
        validate_custom_fields([definition], {"value": 6, "unknown": True})
    assert validate_custom_fields([definition.model_copy(update={"required": False})], {}) == {"value": None}


@pytest.mark.parametrize("operator", ["=", "!=", "<", "<=", ">", ">=", "before", "after", "depends_on"])
def test_supported_operator_vocabulary_is_data_only(operator):
    rule = ConstraintDraft(semantic="unknown", operator=operator, parameters={"text": "__import__('os').system('bad')"})
    preview, mapped = map_constraint(rule, 0, {}, {})
    assert not preview.solver_supported
    assert mapped.enabled is False
    assert mapped.constraint_type == "custom"


@pytest.mark.parametrize("semantic,operator,hardness,params", [
    ("deadline", "before", "hard", {"task_id": "dev", "deadline": DEADLINE}),
    ("dependency", "depends_on", "hard", {"before_task_id": "dev", "after_task_id": "test"}),
    ("resource_capacity", "<=", "hard", {"resource_id": "ravi", "capacity": 1}),
    ("availability", "=", "hard", {"resource_id": "ravi", "available_from": START, "available_until": END}),
    ("max_work_hours", "<=", "hard", {"resource_id": "ravi", "max_hours": 6}),
    ("preferred_resource", "=", "soft", {"task_id": "dev", "resource_id": "ravi"}),
    ("preferred_time", "before", "soft", {"task_id": "dev", "preferred_before": DEADLINE}),
])
def test_explicit_solver_handlers(semantic, operator, hardness, params):
    preview, mapped = map_constraint(ConstraintDraft(semantic=semantic, operator=operator, hardness=hardness, parameters=params),
                                     0, {"dev": 10, "test": 11}, {"ravi": 20})
    assert preview.solver_supported and mapped.enabled
    assert mapped.source == "ai"


def test_operator_without_exact_adapter_stays_disabled():
    preview, mapped = map_constraint(ConstraintDraft(semantic="max_work_hours", operator=">", parameters={"max_hours": 6}), 0, {}, {})
    assert not preview.solver_supported and not mapped.enabled


def test_confirm_creates_normalized_domain_and_disabled_custom(client, actors, provider):
    data = example()
    data["custom_fields"] = [{"name": "max_daily_hours", "type": "integer", "minimum": 1, "maximum": 24}]
    data["custom_values"] = {"max_daily_hours": 6}
    data["constraints"] = [{"semantic": "custom_business_score", "operator": ">=", "parameters": {"score": 2}}]
    response = confirm(client, actors, data)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["created_counts"]["tasks"] == 2
    assert result["created_counts"]["disabled_constraints"] == 2
    full = client.get(f"/api/plans/{result['plan_id']}/full", headers=actors[0]).json()
    assert [task["duration_minutes"] for task in full["tasks"]] == [180, 90]
    assert full["tasks"][1]["requirements"][0]["required_resource_id"] == full["resources"][1]["id"]
    assert full["plan"]["status"] == "draft"
    assert all(rule["enabled"] is False for rule in full["constraints"])
    assert client.get(f"/api/plans/{result['plan_id']}/full", headers=actors[1]).status_code == 404


def test_confirm_requires_affirmative_confirmation(client, actors):
    response = confirm(client, actors, confirmed=False)
    assert response.status_code == 422


def test_confirm_answers_resolve_missing_and_revalidate(client, actors, provider):
    data = example()
    data["tasks"][0]["duration_unit"] = None
    provider.extract.return_value = json.dumps(data)
    preview = parse(client, actors).json()
    assert confirm(client, actors, preview["draft"]).status_code == 422
    bad = confirm(client, actors, preview["draft"], answers=[{"field": "tasks.0.duration_unit", "value": "days"}])
    assert bad.status_code == 422
    good = confirm(client, actors, preview["draft"], answers=[{"field": "tasks.0.duration_unit", "value": "hours"}])
    assert good.status_code == 201, good.text


@pytest.mark.parametrize("change", ["cycle", "duplicate", "unknown", "mismatch", "custom", "window"])
def test_invalid_confirmation_leaves_database_unchanged(client, actors, db_engine, change):
    data = example()
    if change == "cycle":
        data["dependencies"].append({"before_task_id": "test", "after_task_id": "dev"})
    elif change == "duplicate":
        data["resources"][1]["name"] = "DEVELOPERS"
    elif change == "unknown":
        data["requirements"][0]["task_id"] = "foreign"
    elif change == "mismatch":
        data["requirements"][1]["resource_type"] = "vehicle"
    elif change == "custom":
        data["custom_values"] = {"undeclared": 6}
    else:
        data["plan"]["planning_end"] = START
    assert confirm(client, actors, data).status_code == 422
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(Plan)) == 0


def test_dependency_cycle_across_constraint_and_edges(client, actors):
    data = example()
    data["constraints"] = [{"semantic": "dependency", "operator": "depends_on",
        "parameters": {"before_task_id": "test", "after_task_id": "dev"}}]
    assert confirm(client, actors, data).status_code == 422


def test_transaction_rolls_back_children_on_failure(client, actors, db_engine, monkeypatch):
    original = Session.flush
    def fail_on_task(self, *args, **kwargs):
        if any(isinstance(item, Task) for item in self.new):
            raise ValueError("synthetic conversion failure")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Session, "flush", fail_on_task)
    assert confirm(client, actors).status_code == 422
    with Session(db_engine) as db:
        for model in (Plan, Resource, Task):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_anonymous_ai_endpoints_rejected(client, provider):
    assert client.post("/api/ai/parse-plan", json={"text": TEXT}).status_code == 401
    assert client.post("/api/ai/confirm-plan", json={"confirmed": True, "draft": example()}).status_code == 401
    provider.extract.assert_not_called()


def test_cross_user_existing_context_blocked_before_provider(client, actors, provider):
    plan = client.post("/api/plans", json=example()["plan"], headers=actors[1]).json()
    response = parse(client, actors, existing_plan_id=plan["id"], include_context=True)
    assert response.status_code == 404
    provider.extract.assert_not_called()


def test_consented_context_is_separate_never_sent_or_applied(client, actors, provider):
    plan = client.post("/api/plans", json=example()["plan"], headers=actors[0]).json()
    assert parse(client, actors, existing_plan_id=plan["id"], include_context=True).json()["suggested_context"] is None
    client.put("/api/memory/consent", json={"enabled": True}, headers=actors[0])
    client.post("/api/memory", json={"memory_type": "working_hours", "key": "hours", "value": {"start": "09:00"}}, headers=actors[0])
    before = client.get(f"/api/plans/{plan['id']}/full", headers=actors[0]).json()
    result = parse(client, actors, existing_plan_id=plan["id"], include_context=True).json()
    assert result["suggested_context"]["requires_confirmation"] is True
    assert result["suggested_context"]["relevant_context"]
    assert all(call.args == (TEXT,) for call in provider.extract.call_args_list)
    assert client.get(f"/api/plans/{plan['id']}/full", headers=actors[0]).json() == before


@pytest.mark.parametrize("field", ["__class__", "plan.user_id", "tasks.999.name"])
def test_arbitrary_answer_paths_rejected(client, actors, field):
    assert confirm(client, actors, answers=[{"field": field, "value": 1}]).status_code == 422


def settings(**kwargs):
    return GeminiSettings(_env_file=None, gemini_api_key="test-secret-do-not-log", **kwargs)


def test_missing_key_safely_isolated_from_manual_apis(client, actors, application):
    config = GeminiSettings(_env_file=None, gemini_api_key=None)
    application.dependency_overrides[get_gemini_client] = lambda: GeminiClient(config)
    result = parse(client, actors)
    assert result.status_code == 503
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/plans", json=example()["plan"], headers=actors[0]).status_code == 201


@pytest.mark.parametrize("status,expected", [(429, 429), (401, 503), (403, 503), (500, 502), (302, 502)])
def test_provider_status_never_leaks_secret(status, expected, caplog):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"secret": "test-secret-do-not-log"}))
    with pytest.raises(HTTPException) as error:
        GeminiClient(settings(), transport).extract(TEXT)
    assert error.value.status_code == expected
    assert "test-secret-do-not-log" not in str(error.value.detail) + caplog.text


@pytest.mark.parametrize("exception,expected", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_network_and_timeout_are_sanitized(exception, expected):
    def fail(request):
        raise exception("test-secret-do-not-log", request=request)
    with pytest.raises(HTTPException) as error:
        GeminiClient(settings(), httpx.MockTransport(fail)).extract(TEXT)
    assert error.value.status_code == expected
    assert "test-secret" not in str(error.value.detail)


@pytest.mark.parametrize("body", [
    {}, {"status": "completed", "steps": []},
    {"status": "completed", "steps": ["bad"]},
    {"status": "incomplete", "steps": []},
    {"status": "completed", "steps": None},
    {"status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": 42}]}]},
])
def test_malformed_provider_envelope(body):
    with pytest.raises(HTTPException) as error:
        GeminiClient(settings(), httpx.MockTransport(lambda _: httpx.Response(200, json=body))).extract(TEXT)
    assert error.value.status_code == 502


def test_rest_configuration_and_structured_response():
    def serve(request):
        assert "test-secret" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "test-secret-do-not-log"
        payload = json.loads(request.content)
        assert request.url.path == "/v1beta/interactions"
        assert set(payload) == {"model", "input", "system_instruction", "response_format", "generation_config", "store"}
        assert payload["model"] == "gemini-3.6-flash"
        assert payload["store"] is False
        assert payload["generation_config"] == {"max_output_tokens": 16000}
        from app.services.ai.gemini_client import extraction_json_schema, INSTRUCTION
        assert payload["response_format"] == {
            "type": "text", "mime_type": "application/json", "schema": extraction_json_schema(),
        }
        assert payload["input"] == TEXT
        assert payload["system_instruction"] == INSTRUCTION
        return httpx.Response(200, json={"status": "completed", "steps": [
            {"type": "user_input", "content": [{"type": "text", "text": "not the answer"}]},
            {"type": "thought", "summary": [{"type": "text", "text": "not the answer"}]},
            {"type": "model_output", "content": [{"type": "text", "text": json.dumps(example())}]},
        ]})
    result = parse_plan(GeminiClient(settings(), httpx.MockTransport(serve)), TEXT)
    assert result.status == "ready"


@pytest.mark.parametrize("field,value", [("duration_value", 777), ("deadline", "2030-01-01T17:00:00Z")])
def test_invented_quantity_or_date_needs_confirmation(field, value):
    data = example()
    data["tasks"][0][field] = value
    if field == "deadline":
        data["evidence"].append({"field": "tasks.0.deadline", "quote": TEXT})
    result = parse_plan(Mock(extract=Mock(return_value=json.dumps(data))), TEXT)
    assert result.status == "needs_clarification"
    assert any(q.field == "tasks.0." + field for q in result.questions)


def test_available_schema_has_no_recursive_json_reference():
    from app.services.ai.gemini_client import extraction_json_schema
    schema = extraction_json_schema()
    encoded = json.dumps(schema, allow_nan=False)
    for keyword in ("$ref", "$defs", "anyOf", "default", "title"):
        assert '"' + keyword + '"' not in encoded
    assert "parameters_json" in schema["properties"]["constraints"]["items"]["properties"]
    assert "evidence" in schema["properties"]


def test_confirm_rejects_integer_truthiness(client, actors):
    assert confirm(client, actors, confirmed=1).status_code == 422


def test_http_unavailable_and_timeout_reach_api_safely(client, actors, provider):
    for status in (429, 503, 504):
        provider.extract.side_effect = HTTPException(status, "Provider temporarily unavailable")
        result = parse(client, actors)
        assert result.status_code == status
        assert "Traceback" not in result.text


def test_non_json_provider_envelope_is_sanitized():
    client = GeminiClient(settings(), httpx.MockTransport(lambda _: httpx.Response(200, text="not-json")))
    with pytest.raises(HTTPException) as error:
        client.extract(TEXT)
    assert error.value.status_code == 502


def test_confirm_mapped_rule_uses_new_ids_and_solver_still_works(client, actors):
    # Existing records ensure client-ID mapping cannot accidentally rely on IDs starting at one.
    assert confirm(client, actors).status_code == 201
    data = example()
    data["constraints"] = [{"semantic": "deadline", "operator": "before",
        "parameters": {"task_id": "test", "deadline": DEADLINE}}]
    result = confirm(client, actors, data)
    assert result.status_code == 201, result.text
    plan_id = result.json()["plan_id"]
    full = client.get(f"/api/plans/{plan_id}/full", headers=actors[0]).json()
    assert full["constraints"][0]["parameters"]["task_id"] == full["tasks"][1]["id"]
    solved = client.post(f"/api/plans/{plan_id}/solve", json={}, headers=actors[0])
    assert solved.status_code == 200, solved.text
    assert solved.json()["status"] in ("optimal", "feasible")


def test_dynamic_missing_value_asks_question_and_can_be_answered(client, actors):
    data = example()
    data["custom_fields"] = [{"name": "max_daily_hours", "type": "integer", "minimum": 1, "maximum": 24}]
    preview = inspect_draft(PlanningDraft.model_validate(data))
    assert preview.status == "needs_clarification"
    assert any(q.field == "custom_values.max_daily_hours" for q in preview.questions)
    result = confirm(client, actors, preview.draft.model_dump(mode="json"), answers=[
        {"field": "custom_values.max_daily_hours", "value": 6}])
    assert result.status_code == 201, result.text


def test_unknown_soft_semantic_is_preserved_disabled():
    preview, rule = map_constraint(ConstraintDraft(semantic='custom', operator='=', hardness='soft'), 0, {}, {})
    assert not preview.solver_supported and not rule.enabled
    assert rule.weight == 1

def test_large_incomplete_preview_round_trips_through_confirmation_schema():
    from app.schemas.ai_parser import ConfirmPlanRequest
    draft = PlanningDraft.model_validate({
        'plan': {},
        'tasks': [{'client_id': f't{i}'} for i in range(50)],
        'resources': [{'client_id': f'r{i}'} for i in range(30)],
    })
    preview = inspect_draft(draft)
    assert len(preview.questions) > 200
    assert not preview.custom_fields_solver_supported
    confirmed = ConfirmPlanRequest.model_validate({'confirmed': True, 'draft': preview.draft.model_dump(mode='json')})
    assert inspect_draft(confirmed.draft).status == 'needs_clarification'

@pytest.mark.parametrize("status,category,expected", [
    (400, "invalid_request", 502), (401, "authentication", 503),
    (403, "authentication", 503), (404, "model_unavailable", 503),
    (429, "rate_limit", 429), (500, "upstream_server", 502), (503, "upstream_server", 502),
])
def test_live_diagnostics_are_redacted_and_never_returned_to_clients(status, category, expected, caplog):
    message = 'Unsupported schema property. key=test-secret-do-not-log password=private-password'
    transport = httpx.MockTransport(lambda _: httpx.Response(status, json={"error": {"message": message}}))
    client = GeminiClient(settings(), transport)
    with pytest.raises(HTTPException) as error:
        client.extract(TEXT)
    assert error.value.status_code == expected
    assert client.last_failure["upstream_status"] == status
    assert client.last_failure["category"] == category
    assert client.last_failure["model"] == "gemini-3.6-flash"
    assert "Unsupported schema property" in client.last_failure["message"]
    combined = caplog.text + json.dumps(client.last_failure) + str(error.value.detail)
    assert "test-secret-do-not-log" not in combined
    assert "private-password" not in combined
    assert "Unsupported schema property" not in str(error.value.detail)
    if status == 429:
        assert error.value.headers["Retry-After"] == "60"


def test_http_error_bodies_are_bounded_and_not_logged(caplog):
    client = GeminiClient(settings(), httpx.MockTransport(
        lambda _: httpx.Response(400, content=b"x" * 20000)))
    with pytest.raises(HTTPException):
        client.extract(TEXT)
    assert client.last_failure["category"] == "invalid_request"
    assert client.last_failure["message"] == "No structured upstream error message"
    assert "xxxxx" not in caplog.text


def test_configured_model_endpoint_and_no_retries():
    requests = []
    def serve(request):
        requests.append(request)
        assert str(request.url).endswith("/v1beta/interactions")
        assert json.loads(request.content)["model"] == "gemini-test-model"
        assert request.headers["x-goog-api-key"] == "test-secret-do-not-log"
        raise httpx.ReadTimeout("test-secret-do-not-log", request=request)
    client = GeminiClient(settings(gemini_model="gemini-test-model"), httpx.MockTransport(serve))
    with pytest.raises(HTTPException):
        client.extract(TEXT)
    assert len(requests) == 1
    assert client.last_failure["category"] == "timeout"


def test_diagnostics_redact_other_configured_secrets_and_input(caplog):
    private = "private-jwt-secret-with-more-than-32-bytes"
    text = "Private planning instructions."
    message = f"Rejected {text} credential {private}"
    client = GeminiClient(settings(jwt_secret_key=private), httpx.MockTransport(
        lambda _: httpx.Response(400, json={"error": {"message": message}})))
    with pytest.raises(HTTPException):
        client.extract(text)
    assert private not in caplog.text
    assert text not in caplog.text



def test_diagnostics_redact_bearer_header():
    from app.services.ai.gemini_client import sanitize_upstream_message
    message = sanitize_upstream_message('Authorization: Bearer private-token', [])
    assert 'private-token' not in message


@pytest.mark.parametrize("status", ["incomplete", "failed", "requires_action", "in_progress", "cancelled"])
def test_interaction_must_complete_without_followup(status, caplog):
    calls = []
    def serve(request):
        calls.append(request)
        return httpx.Response(200, json={"status": status, "error": {"message": "Rejected test-secret-do-not-log"},
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": "{}"}]}]})
    client = GeminiClient(settings(), httpx.MockTransport(serve))
    with pytest.raises(HTTPException) as error:
        client.extract(TEXT)
    assert error.value.status_code == 502
    assert len(calls) == 1
    assert client.last_failure["category"] == "incomplete_response"
    assert "test-secret-do-not-log" not in caplog.text


def test_completed_interaction_without_model_text_rejected():
    client = GeminiClient(settings(), httpx.MockTransport(lambda _: httpx.Response(200, json={
        "status": "completed", "steps": [{"type": "function_call", "name": "never_execute", "arguments": {}}],
    })))
    with pytest.raises(HTTPException):
        client.extract(TEXT)


def test_model_environment_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    assert GeminiSettings(_env_file=None).gemini_model == "gemini-test-model"


def test_transport_conversion_preserves_full_validation():
    from app.services.ai.gemini_schema import to_planning_json
    data = example()
    data["constraints"] = [{"semantic": "deadline", "operator": "before", "hardness": "hard", "weight": None,
        "parameters_json": json.dumps({"task_id": "test", "deadline": DEADLINE})}]
    draft = PlanningDraft.model_validate_json(to_planning_json(json.dumps(data)))
    assert draft.constraints[0].parameters == {"task_id": "test", "deadline": DEADLINE}
    assert draft.tasks[0].duration_value == Decimal("3")
    assert draft.tasks[1].priority == "critical"
    assert draft.requirements[1].required_resource_id == "ravi"
    assert draft.custom_fields == [] and draft.custom_values == {}


@pytest.mark.parametrize("parameters", ['{"x":1,"x":2}', '{"x":NaN}', '[]', '__import__("os").system("echo unsafe")'])
def test_transport_rejects_invalid_parameter_strings(parameters):
    from app.services.ai.gemini_schema import to_planning_json
    data = example()
    data["constraints"] = [{"semantic": "custom", "operator": "=", "parameters_json": parameters}]
    with pytest.raises(ValueError):
        to_planning_json(json.dumps(data))


@pytest.mark.parametrize("mutation", [
    lambda data: data["tasks"][0].update(duration_value=-1),
    lambda data: data["tasks"][0].update(priority="urgent"),
    lambda data: data["plan"].update(planning_start="tomorrow"),
    lambda data: data.update(unexpected="must not be dropped"),
])
def test_transport_does_not_weaken_domain_validation(mutation):
    from app.services.ai.gemini_schema import to_planning_json
    data = example()
    mutation(data)
    with pytest.raises(ValueError):
        to_planning_json(json.dumps(data))


def test_transport_duplicate_root_and_conflicting_parameters_rejected():
    from app.services.ai.gemini_schema import to_planning_json
    with pytest.raises(ValueError):
        to_planning_json('{"plan":{},"plan":{}}')
    data = example()
    data["constraints"] = [{"semantic": "custom", "operator": "=", "parameters": {}, "parameters_json": "{}"}]
    with pytest.raises(ValueError):
        to_planning_json(json.dumps(data))


def test_transport_preserves_unanchored_deadline_and_ambiguities():
    from app.services.ai.gemini_schema import to_planning_json
    data = example()
    data["tasks"][1]["deadline"] = None
    data["tasks"][1]["deadline_text"] = "5 PM"
    data["resources"][1]["resource_type"] = None
    data["resources"][1]["capacity"] = None
    data["ambiguities"] = [{"field": "resources.1.resource_type", "reason": "Ravi's role is unspecified"}]
    draft = PlanningDraft.model_validate_json(to_planning_json(json.dumps(data)))
    assert draft.tasks[1].deadline is None and draft.tasks[1].deadline_text == "5 PM"
    assert draft.resources[1].capacity is None
    assert inspect_draft(draft).status == "needs_clarification"

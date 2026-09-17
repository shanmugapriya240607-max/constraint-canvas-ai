from unittest.mock import Mock

from sqlalchemy.exc import OperationalError

from app.database import get_db


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "message": "ConstraintCanvas AI Backend",
        "version": "2.0.0", "docs": "/docs", "health": "/api/health",
    }


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "service": "ConstraintCanvas AI Backend",
        "version": "2.0.0", "database": "connected",
    }


def test_health_database_failure(client, application):
    failed_session = Mock()
    failed_session.execute.side_effect = OperationalError(
        "SELECT 1", {}, Exception("private connection details")
    )
    application.dependency_overrides[get_db] = lambda: failed_session
    try:
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json() == {
            "status": "error", "service": "ConstraintCanvas AI Backend",
            "version": "2.0.0", "database": "disconnected",
        }
        assert "private" not in response.text
        failed_session.execute.assert_called_once()
    finally:
        application.dependency_overrides.clear()


def test_unhandled_exception_is_safe(client, application):
    def failing_dependency():
        raise RuntimeError("private server details")

    application.dependency_overrides[get_db] = failing_dependency
    try:
        response = client.get("/api/health")
        assert response.status_code == 500
        assert response.json() == {
            "status": "error", "message": "An unexpected server error occurred.",
        }
        assert "private" not in response.text
    finally:
        application.dependency_overrides.clear()


def test_cors_allows_configured_origin(client):
    response = client.options("/api/health", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unconfigured_origin(client):
    response = client.options("/api/health", headers={
        "Origin": "https://unconfigured.example", "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_api_metadata_and_implemented_scope(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "ConstraintCanvas AI"
    assert schema["info"]["version"] == "2.0.0"
    foundation_paths = {path for path in schema["paths"] if not path.startswith("/api/plans")}
    assert foundation_paths == {"/", "/api/health", "/api/auth/register", "/api/auth/login", "/api/auth/me", "/api/memory/consent", "/api/memory", "/api/memory/{memory_id}", "/api/memory/habits/detect", "/api/memory/habits", "/api/memory/habits/{habit_id}/accept", "/api/memory/habits/{habit_id}/reject", "/api/ai/parse-plan", "/api/ai/confirm-plan"}

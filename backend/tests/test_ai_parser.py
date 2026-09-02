import os
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import ExtractedProblem, Task, Objective
from app.ai_parser import AIValidationError, AITimeoutError

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "openai_configured" in data
    assert data["database"] == "connected"
    assert data["optimizer"] == "available"


def test_solve_empty_input():
    response = client.post("/api/solve", json={"text": ""})
    assert response.status_code == 400
    assert response.json()["detail"] == "Planning text is required."

    response_spaces = client.post("/api/solve", json={"text": "   "})
    assert response_spaces.status_code == 400
    assert response_spaces.json()["detail"] == "Planning text is required."


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_solve_valid_extraction(mock_parse):
    mock_extracted = ExtractedProblem(
        problem_title="Morning office schedule",
        objective=Objective(
            type="LATEST_START",
            description="Start morning routine as late as possible"
        ),
        tasks=[
            Task(
                id="task_1",
                name="Wake up",
                duration_minutes=5,
                source_text="Waking up takes 5 minutes"
            ),
            Task(
                id="task_2",
                name="Get ready",
                duration_minutes=30,
                depends_on=["task_1"],
                source_text="Getting ready takes 30 minutes"
            )
        ],
        missing_information=[],
        ambiguities=[],
        assumptions=[],
        extraction_confidence=0.95
    )
    mock_parse.return_value = mock_extracted

    payload = {"text": "I need to wake up for 5 mins and get ready for 30 mins."}
    response = client.post("/api/solve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "EXTRACTED"
    assert data["problem_title"] == "Morning office schedule"
    assert data["extraction_confidence"] == 0.95
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["id"] == "task_1"


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_solve_missing_duration(mock_parse):
    mock_extracted = ExtractedProblem(
        problem_title="Incomplete morning schedule",
        objective=Objective(type="EARLIEST_FINISH"),
        tasks=[
            Task(
                id="task_1",
                name="Wake up",
                duration_minutes=None,
                source_text="I need to wake up"
            )
        ],
        missing_information=["How many minutes does waking up take?"],
        extraction_confidence=0.8
    )
    mock_parse.return_value = mock_extracted

    payload = {"text": "I need to wake up"}
    response = client.post("/api/solve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "NEEDS_INPUT"
    assert data["message"] == "More information is required before optimization."
    assert "How many minutes does waking up take?" in data["questions"]


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_solve_ai_validation_error(mock_parse):
    mock_parse.side_effect = AIValidationError("Schema invalid")

    payload = {"text": "Random text causing invalid parse"}
    response = client.post("/api/solve", json=payload)
    assert response.status_code == 522 or response.status_code == 502
    assert "invalid planning structure" in response.json()["detail"]


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_solve_openai_timeout(mock_parse):
    mock_parse.side_effect = AITimeoutError("Timeout")

    payload = {"text": "Some text"}
    response = client.post("/api/solve", json=payload)
    assert response.status_code == 502
    assert "temporarily unavailable" in response.json()["detail"]

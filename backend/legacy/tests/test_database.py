import os
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db, SolveRun, init_db
from app.schemas import ExtractedProblem, Task, Objective

from sqlalchemy.pool import StaticPool

# Setup isolated in-memory SQLite engine for tests using StaticPool so threads share the same database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)



def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_db_table_creation():
    db = TestingSessionLocal()
    count = db.query(SolveRun).count()
    assert count == 0
    db.close()


def test_health_with_database():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_save_optimal_run(mock_parse):
    mock_extracted = ExtractedProblem(
        problem_title="Optimal Test Schedule",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Task A", duration_minutes=10),
            Task(id="task_2", name="Task B", duration_minutes=20, depends_on=["task_1"])
        ],
        extraction_confidence=0.99
    )
    mock_parse.return_value = mock_extracted

    payload = {"text": "Do Task A then Task B."}
    response = client.post("/api/solve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("OPTIMAL", "FEASIBLE")

    db = TestingSessionLocal()
    run = db.query(SolveRun).first()
    assert run is not None
    assert run.problem_title == "Optimal Test Schedule"
    assert run.status in ("OPTIMAL", "FEASIBLE")
    assert run.original_text == "Do Task A then Task B."
    db.close()


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_save_infeasible_run(mock_parse):
    mock_extracted = ExtractedProblem(
        problem_title="Infeasible Test Schedule",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Task Impossible", duration_minutes=120, earliest_start="08:00", deadline="09:00")
        ],
        extraction_confidence=0.9
    )
    mock_parse.return_value = mock_extracted

    payload = {"text": "Impossible task."}
    response = client.post("/api/solve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "INFEASIBLE"

    db = TestingSessionLocal()
    run = db.query(SolveRun).first()
    assert run is not None
    assert run.status == "INFEASIBLE"
    db.close()


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_save_needs_input_run(mock_parse):
    mock_extracted = ExtractedProblem(
        problem_title="Incomplete Task",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Task No Duration", duration_minutes=None)
        ],
        missing_information=["How long does Task No Duration take?"],
        extraction_confidence=0.8
    )
    mock_parse.return_value = mock_extracted

    payload = {"text": "Task No Duration."}
    response = client.post("/api/solve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "NEEDS_INPUT"

    db = TestingSessionLocal()
    run = db.query(SolveRun).first()
    assert run is not None
    assert run.status == "NEEDS_INPUT"
    db.close()


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_history_newest_first_and_omits_original_text(mock_parse):
    mock_extracted = ExtractedProblem(
        problem_title="First Run",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[Task(id="t1", name="T1", duration_minutes=10)],
        extraction_confidence=1.0
    )
    mock_parse.return_value = mock_extracted

    client.post("/api/solve", json={"text": "First problem text"})

    mock_extracted_2 = ExtractedProblem(
        problem_title="Second Run",
        objective=Objective(type="EARLIEST_FINISH"),
        tasks=[Task(id="t2", name="T2", duration_minutes=15)],
        extraction_confidence=1.0
    )
    mock_parse.return_value = mock_extracted_2

    client.post("/api/solve", json={"text": "Second problem text"})

    res = client.get("/api/history")
    assert res.status_code == 200
    history_data = res.json()
    assert history_data["count"] == 2
    runs = history_data["runs"]
    assert runs[0]["problem_title"] == "Second Run"
    assert runs[1]["problem_title"] == "First Run"

    # Verify history list items do NOT contain original_text
    assert "original_text" not in runs[0]


@patch("app.main.parse_planning_text")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock_key"})
def test_history_detail_parsed_json(mock_parse):
    mock_extracted = ExtractedProblem(
        problem_title="Detail Test",
        objective=Objective(type="LATEST_START"),
        tasks=[Task(id="t1", name="Detail Task", duration_minutes=25)],
        extraction_confidence=0.95
    )
    mock_parse.return_value = mock_extracted

    solve_res = client.post("/api/solve", json={"text": "Detail test input text."})
    assert solve_res.status_code == 200

    hist_res = client.get("/api/history")
    run_id = hist_res.json()["runs"][0]["id"]

    detail_res = client.get(f"/api/history/{run_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == run_id
    assert detail["original_text"] == "Detail test input text."
    assert detail["problem_title"] == "Detail Test"
    # Verify result and extracted_data are returned as parsed JSON objects (dicts)
    assert isinstance(detail["extracted_data"], dict)
    assert isinstance(detail["result"], dict)


def test_history_not_found():
    res = client.get("/api/history/99999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Solve run not found."

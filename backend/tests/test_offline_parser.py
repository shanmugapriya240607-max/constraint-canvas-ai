import pytest
from unittest.mock import patch
from app.ai_parser import parse_planning_text, parse_planning_text_offline, AIValidationError
from app.validator import validate_extracted_problem
from app.priority_engine import calculate_task_priorities
from app.solver import solve_schedule
from app.database import init_db, SessionLocal, SolveRun
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, declarative_base

OFFICE_DEMO_TEXT = (
    "Tomorrow I must reach the office by 9:00 AM. Waking up takes 10 minutes, "
    "getting ready takes 30 minutes, eating breakfast takes 20 minutes, and travelling to the office takes 40 minutes. "
    "Waking up must finish before getting ready, getting ready must finish before breakfast, and breakfast must finish before travelling to the office."
)

STUDY_DEMO_TEXT = (
    "I must submit my assignment before 6:00 PM. Research takes 45 minutes, writing takes 90 minutes, "
    "proofreading takes 20 minutes, and submission takes 5 minutes. "
    "Research must finish before writing, writing must finish before proofreading, and proofreading must finish before submission."
)

HOURS_DEMO_TEXT = (
    "Physics takes 1.5 hours. Mathematics takes 45 minutes. Physics must finish before Mathematics."
)


def test_offline_parser_no_openai_call_made():
    """Verify offline parser executes cleanly without invoking OpenAI SDK or internet."""
    with patch("openai.OpenAI") as mock_openai:
        with patch.dict("os.environ", {"PARSER_MODE": "offline"}):
            result = parse_planning_text(OFFICE_DEMO_TEXT)
            mock_openai.assert_not_called()
            assert result.parser_mode == "OFFLINE_RULES"
            assert len(result.tasks) == 4
            assert result.tasks[0].id == "task_1"
            assert result.tasks[1].id == "task_2"


def test_offline_parser_hours_conversion_and_deadlines():
    """Verify hours conversion (1.5 hours = 90m) and 12-hour AM/PM & 24-hour deadline parsing."""
    res_hours = parse_planning_text_offline(HOURS_DEMO_TEXT)
    t_physics = [t for t in res_hours.tasks if "physics" in t.name.lower()][0]
    assert t_physics.duration_minutes == 90

    res_office = parse_planning_text_offline(OFFICE_DEMO_TEXT)
    # 9:00 AM should convert to 09:00
    t_travel = [t for t in res_office.tasks if "travelling" in t.name.lower() or "office" in t.name.lower()][0]
    assert t_travel.deadline == "09:00"

    res_study = parse_planning_text_offline(STUDY_DEMO_TEXT)
    # 6:00 PM should convert to 18:00
    t_sub = [t for t in res_study.tasks if "submission" in t.name.lower()][0]
    assert t_sub.deadline == "18:00"


def test_offline_parser_dependency_ordering():
    """Verify before, after, and then relationship extraction."""
    res_study = parse_planning_text_offline(STUDY_DEMO_TEXT)

    t_res = [t for t in res_study.tasks if "research" in t.name.lower()][0]
    t_wri = [t for t in res_study.tasks if "writing" in t.name.lower()][0]
    t_pro = [t for t in res_study.tasks if "proofreading" in t.name.lower()][0]
    t_sub = [t for t in res_study.tasks if "submission" in t.name.lower()][0]

    assert t_res.id in t_wri.depends_on
    assert t_wri.id in t_pro.depends_on
    assert t_pro.id in t_sub.depends_on


def test_offline_parser_missing_duration_rejection():
    """Verify text missing explicit durations raises validation error."""
    text_missing = "I need to wake up, get ready, eat breakfast, and travel to office."
    with pytest.raises(AIValidationError) as excinfo:
        parse_planning_text_offline(text_missing)
    assert "missing explicit durations" in str(excinfo.value)


def test_offline_parser_end_to_end_pipeline_and_sqlite():
    """Verify output passes through validator, priority engine, OR-Tools, and SQLite."""
    extracted = parse_planning_text_offline(OFFICE_DEMO_TEXT)
    assert extracted.parser_mode == "OFFLINE_RULES"

    # Validator
    val_res = validate_extracted_problem(extracted)
    assert val_res.valid is True

    # Priority Engine
    p_tasks = calculate_task_priorities(extracted.tasks)
    assert len(p_tasks) == 4

    # Solver
    status, scheduled, makespan, explanation = solve_schedule(extracted, p_tasks)
    assert status == "OPTIMAL"
    assert len(scheduled) == 4

    # SQLite
    test_engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    init_db(custom_engine=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db = TestSession()

    run_entry = SolveRun(
        original_text=OFFICE_DEMO_TEXT,
        problem_title=extracted.problem_title,
        status=status,
        result_json="{}",
    )
    db.add(run_entry)
    db.commit()

    saved_run = db.query(SolveRun).first()
    assert saved_run is not None
    assert saved_run.status == "OPTIMAL"

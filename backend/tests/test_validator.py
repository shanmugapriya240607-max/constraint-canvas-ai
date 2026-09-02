import pytest
from app.validator import hhmm_to_minutes, minutes_to_hhmm, validate_extracted_problem
from app.schemas import ExtractedProblem, Task, Objective


def test_hhmm_time_conversion():
    assert hhmm_to_minutes("07:25") == 445
    assert minutes_to_hhmm(445) == "07:25"
    assert hhmm_to_minutes("00:00") == 0
    assert minutes_to_hhmm(0) == "00:00"
    assert hhmm_to_minutes("23:59") == 1439
    assert minutes_to_hhmm(1439) == "23:59"

    with pytest.raises(ValueError):
        hhmm_to_minutes("25:90")

    with pytest.raises(ValueError):
        hhmm_to_minutes("invalid")

    with pytest.raises(ValueError):
        minutes_to_hhmm(1500)


def test_valid_dependency_chain():
    problem = ExtractedProblem(
        problem_title="Valid Chain",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Step 1", duration_minutes=10),
            Task(id="task_2", name="Step 2", duration_minutes=20, depends_on=["task_1"])
        ],
        extraction_confidence=1.0
    )
    res = validate_extracted_problem(problem)
    assert res.valid is True
    assert len(res.errors) == 0


def test_unknown_dependency():
    problem = ExtractedProblem(
        problem_title="Unknown Dep",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Step 1", duration_minutes=10, depends_on=["non_existent_id"])
        ],
        extraction_confidence=1.0
    )
    res = validate_extracted_problem(problem)
    assert res.valid is False
    assert any(e.code == "UNKNOWN_DEPENDENCY" for e in res.errors)


def test_self_dependency():
    problem = ExtractedProblem(
        problem_title="Self Dep",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Step 1", duration_minutes=10, depends_on=["task_1"])
        ],
        extraction_confidence=1.0
    )
    res = validate_extracted_problem(problem)
    assert res.valid is False
    assert any(e.code == "SELF_DEPENDENCY" for e in res.errors)


def test_circular_dependency():
    problem = ExtractedProblem(
        problem_title="Circular Dep",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Step 1", duration_minutes=10, depends_on=["task_2"]),
            Task(id="task_2", name="Step 2", duration_minutes=20, depends_on=["task_1"])
        ],
        extraction_confidence=1.0
    )
    res = validate_extracted_problem(problem)
    assert res.valid is False
    assert any(e.code == "CIRCULAR_DEPENDENCY" for e in res.errors)


def test_duplicate_task_id():
    # Pydantic schema model validator catches duplicate task IDs
    with pytest.raises(ValueError, match="Duplicate task ID"):
        ExtractedProblem(
            problem_title="Duplicate ID",
            objective=Objective(type="MINIMIZE_MAKESPAN"),
            tasks=[
                Task(id="task_1", name="Step 1", duration_minutes=10),
                Task(id="task_1", name="Step 1 Duplicate", duration_minutes=10)
            ],
            extraction_confidence=1.0
        )


def test_missing_duration():
    problem = ExtractedProblem(
        problem_title="Missing Duration",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Step 1", duration_minutes=None)
        ],
        extraction_confidence=1.0
    )
    res = validate_extracted_problem(problem)
    assert res.valid is False
    assert any(e.code == "MISSING_DURATION" for e in res.errors)


def test_invalid_time_format():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Task(id="task_1", name="Step 1", duration_minutes=10, earliest_start="26:00")


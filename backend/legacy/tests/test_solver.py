import pytest
from app.schemas import ExtractedProblem, Task, Objective
from app.priority_engine import calculate_task_priorities
from app.solver import solve_schedule


def test_office_example_latest_start_schedule():
    """
    Office verification example from spec:
    - Objective: LATEST_START
    - Wake up: 5 min, depends []
    - Get ready: 30 min, depends [Wake up]
    - Eat breakfast: 20 min, depends [Get ready]
    - Travel to office: 40 min, deadline "09:00", depends [Eat breakfast]
    
    Expected Schedule:
    - Wake up: 07:25–07:30
    - Get ready: 07:30–08:00
    - Eat breakfast: 08:00–08:20
    - Travel to office: 08:20–09:00
    - Total makespan: 95 min
    """
    problem = ExtractedProblem(
        problem_title="Morning office schedule",
        objective=Objective(type="LATEST_START", description="Start routine as late as possible"),
        tasks=[
            Task(id="task_1", name="Wake up", duration_minutes=5, depends_on=[], resources=["person"]),
            Task(id="task_2", name="Get ready", duration_minutes=30, depends_on=["task_1"], resources=["person"]),
            Task(id="task_3", name="Eat breakfast", duration_minutes=20, depends_on=["task_2"], resources=["person"]),
            Task(id="task_4", name="Travel to office", duration_minutes=40, deadline="09:00", depends_on=["task_3"], resources=["person"]),
        ],
        extraction_confidence=0.95
    )

    prioritized = calculate_task_priorities(problem.tasks)
    status, scheduled, makespan, explanation = solve_schedule(problem, prioritized)

    assert status == "OPTIMAL"
    assert makespan == 540  # 09:00 AM = 540 minutes from midnight

    task_by_id = {t.id: t for t in scheduled}
    assert task_by_id["task_1"].start == "07:25"
    assert task_by_id["task_1"].end == "07:30"

    assert task_by_id["task_2"].start == "07:30"
    assert task_by_id["task_2"].end == "08:00"

    assert task_by_id["task_3"].start == "08:00"
    assert task_by_id["task_3"].end == "08:20"

    assert task_by_id["task_4"].start == "08:20"
    assert task_by_id["task_4"].end == "09:00"


def test_earliest_finish_schedule():
    problem = ExtractedProblem(
        problem_title="Study schedule",
        objective=Objective(type="EARLIEST_FINISH"),
        tasks=[
            Task(id="task_1", name="Math", duration_minutes=45, earliest_start="18:00", resources=["person"]),
            Task(id="task_2", name="Physics", duration_minutes=30, depends_on=["task_1"], resources=["person"]),
            Task(id="task_3", name="Reading", duration_minutes=20, earliest_start="18:00", resources=["person"])
        ],
        extraction_confidence=1.0
    )

    prioritized = calculate_task_priorities(problem.tasks)
    status, scheduled, makespan, explanation = solve_schedule(problem, prioritized)

    assert status in ("OPTIMAL", "FEASIBLE")
    # Verify tasks do not overlap on person resource
    person_intervals = []
    for t in scheduled:
        sh, sm = map(int, t.start.split(":"))
        eh, em = map(int, t.end.split(":"))
        person_intervals.append((sh * 60 + sm, eh * 60 + em))

    person_intervals.sort(key=lambda x: x[0])
    for i in range(len(person_intervals) - 1):
        assert person_intervals[i][1] <= person_intervals[i+1][0]


def test_infeasible_deadline():
    problem = ExtractedProblem(
        problem_title="Infeasible Schedule",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Long task", duration_minutes=120, earliest_start="08:00", deadline="09:00", resources=["person"])
        ],
        extraction_confidence=1.0
    )

    prioritized = calculate_task_priorities(problem.tasks)
    status, scheduled, makespan, explanation = solve_schedule(problem, prioritized)

    assert status == "INFEASIBLE"
    assert "No feasible schedule found" in explanation


def test_resource_non_overlap():
    problem = ExtractedProblem(
        problem_title="Resource Non-Overlap",
        objective=Objective(type="MINIMIZE_MAKESPAN"),
        tasks=[
            Task(id="task_1", name="Task A", duration_minutes=30, earliest_start="08:00", resources=["person"]),
            Task(id="task_2", name="Task B", duration_minutes=30, earliest_start="08:00", resources=["person"])
        ],
        extraction_confidence=1.0
    )

    prioritized = calculate_task_priorities(problem.tasks)
    status, scheduled, makespan, explanation = solve_schedule(problem, prioritized)

    assert status in ("OPTIMAL", "FEASIBLE")
    t1 = scheduled[0] if scheduled[0].id == "task_1" else scheduled[1]
    t2 = scheduled[1] if scheduled[0].id == "task_1" else scheduled[0]
    
    t1_end = int(t1.end.split(":")[0]) * 60 + int(t1.end.split(":")[1])
    t2_start = int(t2.start.split(":")[0]) * 60 + int(t2.start.split(":")[1])

    t2_end = int(t2.end.split(":")[0]) * 60 + int(t2.end.split(":")[1])
    t1_start = int(t1.start.split(":")[0]) * 60 + int(t1.start.split(":")[1])

    assert (t1_end <= t2_start) or (t2_end <= t1_start)


def test_priority_of_root_dependency_and_hard_override():
    tasks = [
        Task(id="task_1", name="Wake up", duration_minutes=5, depends_on=[]),
        Task(id="task_2", name="Get ready", duration_minutes=30, depends_on=["task_1"]),
        Task(id="task_3", name="Breakfast", duration_minutes=20, depends_on=["task_2"]),
        Task(id="task_4", name="Travel", duration_minutes=40, depends_on=["task_3"])
    ]

    prioritized = calculate_task_priorities(tasks)
    
    # Root task unlocking 3 downstream tasks must have execution_level 1 and high priority
    wake_up = next(t for t in prioritized if t.id == "task_1")
    travel = next(t for t in prioritized if t.id == "task_4")

    assert wake_up.execution_level == 1
    assert travel.execution_level == 4
    assert wake_up.priority_score > travel.priority_score

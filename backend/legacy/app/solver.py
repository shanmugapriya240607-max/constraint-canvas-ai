from typing import List, Tuple, Optional, Dict
from ortools.sat.python import cp_model
from app.schemas import ExtractedProblem, Task, Objective
from app.validator import hhmm_to_minutes, minutes_to_hhmm


def solve_schedule(problem: ExtractedProblem, tasks: List[Task]) -> Tuple[str, List[Task], Optional[int], Optional[str]]:
    """
    Solves task scheduling problem using Google OR-Tools CP-SAT engine.
    Enforces dependencies, earliest starts, deadlines, and resource non-overlap constraints.
    Supports MINIMIZE_MAKESPAN, EARLIEST_FINISH, and LATEST_START objectives.
    """
    if not tasks:
        return "OPTIMAL", [], 0, "No tasks to schedule."

    model = cp_model.CpModel()
    task_map: Dict[str, Task] = {t.id: t for t in tasks}

    # 1. Variables
    start_vars: Dict[str, cp_model.IntVar] = {}
    end_vars: Dict[str, cp_model.IntVar] = {}
    interval_vars: Dict[str, cp_model.IntervalVar] = {}

    HORIZON = 1439  # Minutes in a day (0..1439)

    for t in tasks:
        duration = t.duration_minutes or 0
        s_var = model.NewIntVar(0, HORIZON, f"start_{t.id}")
        e_var = model.NewIntVar(0, HORIZON, f"end_{t.id}")
        i_var = model.NewIntervalVar(s_var, duration, e_var, f"interval_{t.id}")

        start_vars[t.id] = s_var
        end_vars[t.id] = e_var
        interval_vars[t.id] = i_var

        # 2. Earliest start constraint
        if t.earliest_start:
            try:
                es_min = hhmm_to_minutes(t.earliest_start)
                model.Add(s_var >= es_min)
            except ValueError:
                pass

        # 3. Deadline constraint
        if t.deadline:
            try:
                dl_min = hhmm_to_minutes(t.deadline)
                model.Add(e_var <= dl_min)
            except ValueError:
                pass

    # 4. Dependency constraints: predecessor_end <= successor_start
    for t in tasks:
        for dep_id in t.depends_on:
            if dep_id in end_vars:
                model.Add(end_vars[dep_id] <= start_vars[t.id])

    # 5. Exclusive resource non-overlap constraints
    # Group intervals by resource name
    resource_intervals: Dict[str, List[cp_model.IntervalVar]] = {}
    for t in tasks:
        # Passive tasks do not block person resource unless stated
        for res in t.resources:
            res_lower = res.strip().lower()
            if res_lower == "person" and t.is_passive:
                continue  # Skip blocking person for passive task
            if res_lower not in resource_intervals:
                resource_intervals[res_lower] = []
            resource_intervals[res_lower].append(interval_vars[t.id])

    for res_name, intervals in resource_intervals.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)

    # 6. Objective handling
    obj_type = problem.objective.type if problem.objective else "MINIMIZE_MAKESPAN"

    makespan_var = model.NewIntVar(0, HORIZON, "makespan")
    model.AddMaxEquality(makespan_var, list(end_vars.values()))

    if obj_type == "LATEST_START":
        # Schedule start = start time of root task(s)
        root_task_ids = [t.id for t in tasks if not t.depends_on]
        if root_task_ids:
            sched_start_var = model.NewIntVar(0, HORIZON, "sched_start")
            root_starts = [start_vars[tid] for tid in root_task_ids]
            model.AddMinEquality(sched_start_var, root_starts)
            # Maximize root task start time while satisfying all deadlines
            model.Maximize(sched_start_var)
        else:
            model.Minimize(makespan_var)
    elif obj_type in ("MINIMIZE_MAKESPAN", "EARLIEST_FINISH"):
        model.Minimize(makespan_var)
    else:
        model.Minimize(makespan_var)

    # 7. Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status_code = solver.Solve(model)

    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        status = "OPTIMAL" if status_code == cp_model.OPTIMAL else "FEASIBLE"
        scheduled_tasks: List[Task] = []

        for t in tasks:
            start_min = solver.Value(start_vars[t.id])
            end_min = solver.Value(end_vars[t.id])

            start_str = minutes_to_hhmm(start_min)
            end_str = minutes_to_hhmm(end_min)

            scheduled_task = t.model_copy(update={
                "start": start_str,
                "end": end_str
            })
            scheduled_tasks.append(scheduled_task)

        # Sort scheduled tasks by start time then execution level
        scheduled_tasks.sort(key=lambda x: (hhmm_to_minutes(x.start or "00:00"), x.execution_level or 1))
        makespan_val = solver.Value(makespan_var)

        explanation = f"Successfully generated {status.lower()} schedule for {len(scheduled_tasks)} tasks satisfying all constraints."
        return status, scheduled_tasks, makespan_val, explanation

    elif status_code == cp_model.INFEASIBLE:
        explanation = "No feasible schedule found — check your constraints. The required tasks cannot fit before the stated deadline or resource limits."
        return "INFEASIBLE", [], None, explanation

    else:
        explanation = "The optimization solver returned UNKNOWN. Schedule could not be proven."
        return "UNKNOWN", [], None, explanation

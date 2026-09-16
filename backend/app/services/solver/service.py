"""Snapshot, solve, and atomically persist result and plan status."""
import ortools
from pydantic import ValidationError

from app.models import SolverRun
from app.services.planning import full_plan
from app.services.solver.cp_sat_solver import solve
from app.services.solver.input_builder import SolverInputError, build_input


def solve_plan(db, plan, options):
    # Caller holds the plan write lock so persisted inputs cannot change mid-solve.
    try:
        snapshot = full_plan(db,plan)
    except (ValidationError, ValueError) as exc:
        raise SolverInputError("Stored planning records are invalid") from exc
    result = solve(build_input(snapshot),options.max_solve_seconds)
    if result.status in ("optimal","feasible"):
        plan.status = "solved"
    elif result.status == "infeasible":
        plan.status = "infeasible"
    record = SolverRun(plan_id=plan.id,solver_status=result.status,
        makespan_minutes=result.metrics.makespan_minutes,solve_duration_ms=result.metrics.solver_wall_time_ms,
        solver_version=ortools.__version__,result={},input_snapshot=snapshot.model_dump(mode="json"))
    db.add(record)
    db.flush()
    result.run_id = record.id
    record.result = result.model_dump(mode="json")
    db.commit()
    return result

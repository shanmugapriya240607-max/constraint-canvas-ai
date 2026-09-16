"""Authenticated solver and immutable run-history endpoints."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies.ownership import Database, OwnedPlan, PathID, WritablePlan, get_nested
from app.models import SolverRun
from app.schemas.solver import SolveRequest, SolveResponse, SolverRunDetail, SolverRunSummary
from app.services.solver.input_builder import SolverInputError
from app.services.solver.service import solve_plan

router = APIRouter(prefix="/api/plans",tags=["solver"])


@router.post("/{plan_id}/solve",response_model=SolveResponse)
def solve_endpoint(plan: WritablePlan,db: Database,payload: SolveRequest | None = None):
    try:
        return solve_plan(db,plan,payload or SolveRequest())
    except SolverInputError as exc:
        raise HTTPException(status_code=422,detail={"code":"invalid_solver_input","message":str(exc)}) from None


@router.get("/{plan_id}/runs",response_model=list[SolverRunSummary])
def list_runs(plan: OwnedPlan,db: Database):
    return db.scalars(select(SolverRun).where(SolverRun.plan_id == plan.id).order_by(SolverRun.id.desc())).all()


@router.get("/{plan_id}/runs/{run_id}",response_model=SolverRunDetail)
def read_run(run_id: PathID,plan: OwnedPlan,db: Database):
    return get_nested(db,SolverRun,run_id,plan_id=plan.id)

import os
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv

from app.schemas import (
    PlanningRequest,
    SolveResponse,
    ExtractedProblem,
    HistoryListResponse,
    SolveRunHistoryItem,
    SolveRunDetailResponse,
)
from app.ai_parser import (
    parse_planning_text,
    AIParserError,
    AIConfigurationError,
    AITimeoutError,
    AIValidationError,
)
from app.validator import validate_extracted_problem
from app.priority_engine import calculate_task_priorities
from app.solver import solve_schedule
from app.database import init_db, get_db, SolveRun

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ConstraintCanvas AI API",
    description="Natural-Language Planning and Optimization API",
    version="1.0.0",
)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

origins = [
    frontend_origin,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database tables on module import
try:
    init_db()
    logger.info("Database initialized successfully.")
except Exception as exc:
    logger.error(f"Database initialization error: {exc}")



@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    openai_key = os.getenv("OPENAI_API_KEY")

    db_status = "disconnected"
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error(f"Health check DB probe error: {exc}")
        db_status = "disconnected"

    return {
        "status": "healthy",
        "openai_configured": bool(openai_key and openai_key.strip()),
        "database": db_status,
        "optimizer": "available",
    }


def _safe_json_dumps(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    try:
        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)


def _safe_json_loads(json_str: Optional[str]) -> Any:
    if not json_str or not json_str.strip():
        return None
    try:
        return json.loads(json_str)
    except Exception:
        return json_str


@app.post("/api/solve", response_model=SolveResponse)
def solve_planning_problem(request: PlanningRequest, db: Session = Depends(get_db)):
    # 1. Request Validation
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planning text is required.",
        )

    try:
        # 2. ChatGPT extraction & Pydantic validation
        extracted: ExtractedProblem = parse_planning_text(request.text)

        # 3. Missing information check
        missing_questions = list(extracted.missing_information)
        for task in extracted.tasks:
            if task.duration_minutes is None:
                q = f"How many minutes does task '{task.name}' take?"
                if q not in missing_questions:
                    missing_questions.append(q)

        if missing_questions:
            solve_res = SolveResponse(
                status="NEEDS_INPUT",
                message="More information is required before optimization.",
                questions=missing_questions,
                tasks=extracted.tasks,
            )
            _persist_run(db, request.text, extracted, "NEEDS_INPUT", solve_res)
            return solve_res

        # 4. Deterministic validation
        val_result = validate_extracted_problem(extracted)
        if not val_result.valid:
            solve_res = SolveResponse(
                status="INVALID",
                message="The planning model contains invalid constraints.",
                errors=val_result.errors,
                tasks=[],
            )
            _persist_run(db, request.text, extracted, "INVALID", solve_res)
            return solve_res

        # 5. Priority calculation
        prioritized_tasks = calculate_task_priorities(extracted.tasks)

        # 6. OR-Tools optimization
        solve_status, scheduled_tasks, makespan, explanation = solve_schedule(extracted, prioritized_tasks)

        if solve_status == "INFEASIBLE":
            solve_res = SolveResponse(
                status="INFEASIBLE",
                message="No feasible schedule found — check your constraints.",
                explanation=explanation,
                tasks=[],
            )
            _persist_run(db, request.text, extracted, "INFEASIBLE", solve_res)
            return solve_res

        # 7. Structured Response
        solve_res = SolveResponse(
            status=solve_status,
            problem_title=extracted.problem_title,
            objective=extracted.objective,
            extraction_confidence=extracted.extraction_confidence,
            makespan_minutes=makespan,
            tasks=scheduled_tasks,
            explanation=explanation,
        )
        _persist_run(db, request.text, extracted, solve_status, solve_res)
        return solve_res

    except AIConfigurationError as exc:
        logger.error(f"Configuration error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenAI API key is not configured.",
        )

    except AITimeoutError as exc:
        logger.error(f"Timeout error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The intelligence service is temporarily unavailable. Please try again.",
        )

    except AIValidationError as exc:
        logger.error(f"Validation error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The intelligence service returned an invalid planning structure. Please try again.",
        )

    except AIParserError as exc:
        logger.error(f"AI parser error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The intelligence service encountered an error processing your request.",
        )

    except Exception as exc:
        logger.error(f"Unexpected error in /api/solve: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred. Please try again.",
        )


def _persist_run(
    db: Session,
    original_text: str,
    extracted: Optional[ExtractedProblem],
    status_str: str,
    response: SolveResponse,
):
    """Safely saves a completed solve run to SQLite. Never raises an exception."""
    try:
        obj_repr = None
        if extracted and extracted.objective:
            obj_repr = extracted.objective.type
        elif response.objective:
            obj_repr = response.objective if isinstance(response.objective, str) else _safe_json_dumps(response.objective)

        problem_title = extracted.problem_title if extracted else response.problem_title
        extracted_data = extracted.model_dump(mode="json") if extracted else None
        result_data = response.model_dump(mode="json")

        run_entry = SolveRun(
            original_text=original_text,
            problem_title=problem_title,
            objective=obj_repr,
            extracted_json=_safe_json_dumps(extracted_data),
            status=status_str,
            result_json=_safe_json_dumps(result_data),
            error_json=_safe_json_dumps([e.model_dump(mode="json") for e in response.errors]) if response.errors else None,
        )
        db.add(run_entry)
        db.commit()
        db.refresh(run_entry)
        response.history_saved = True

    except Exception as exc:
        logger.error(f"Failed to save solve run history: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        response.history_saved = False
        response.warnings = (response.warnings or []) + ["The schedule was generated, but the run could not be saved."]


@app.get("/api/history", response_model=HistoryListResponse)
def get_solve_history(db: Session = Depends(get_db)):
    try:
        runs = (
            db.query(SolveRun)
            .order_by(SolveRun.id.desc())
            .limit(50)
            .all()
        )

        history_items: List[SolveRunHistoryItem] = []
        for r in runs:
            # Determine task count from result or extracted data
            task_count = 0
            res_parsed = _safe_json_loads(r.result_json)
            if isinstance(res_parsed, dict) and "tasks" in res_parsed and isinstance(res_parsed["tasks"], list):
                task_count = len(res_parsed["tasks"])
            else:
                ext_parsed = _safe_json_loads(r.extracted_json)
                if isinstance(ext_parsed, dict) and "tasks" in ext_parsed and isinstance(ext_parsed["tasks"], list):
                    task_count = len(ext_parsed["tasks"])

            obj_val = _safe_json_loads(r.objective)

            created_str = r.created_at.isoformat() if r.created_at else ""

            item = SolveRunHistoryItem(
                id=r.id,
                problem_title=r.problem_title,
                objective=obj_val,
                status=r.status,
                created_at=created_str,
                task_count=task_count,
            )
            history_items.append(item)

        return HistoryListResponse(count=len(history_items), runs=history_items)

    except Exception as exc:
        logger.error(f"Failed to fetch history list: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve solve history.",
        )


@app.get("/api/history/{run_id}", response_model=SolveRunDetailResponse)
def get_solve_run_detail(run_id: int, db: Session = Depends(get_db)):
    try:
        run = db.query(SolveRun).filter(SolveRun.id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solve run not found.",
            )

        obj_val = _safe_json_loads(run.objective)
        extracted_val = _safe_json_loads(run.extracted_json)
        result_val = _safe_json_loads(run.result_json)
        errors_val = _safe_json_loads(run.error_json)
        created_str = run.created_at.isoformat() if run.created_at else ""

        return SolveRunDetailResponse(
            id=run.id,
            original_text=run.original_text,
            problem_title=run.problem_title,
            objective=obj_val,
            extracted_data=extracted_val,
            status=run.status,
            result=result_val,
            errors=errors_val,
            created_at=created_str,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to fetch run detail for id {run_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve solve run detail.",
        )

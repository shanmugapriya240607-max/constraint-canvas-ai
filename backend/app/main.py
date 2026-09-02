import os
import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.schemas import PlanningRequest, SolveResponse, ExtractedProblem
from app.ai_parser import (
    parse_planning_text,
    AIParserError,
    AIConfigurationError,
    AITimeoutError,
    AIValidationError,
)

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


@app.get("/api/health")
def health_check():
    openai_key = os.getenv("OPENAI_API_KEY")
    return {
        "status": "healthy",
        "openai_configured": bool(openai_key and openai_key.strip()),
        "database": "connected",
        "optimizer": "available",
    }


@app.post("/api/solve", response_model=SolveResponse)
def solve_planning_problem(request: PlanningRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planning text is required.",
        )

    try:
        extracted: ExtractedProblem = parse_planning_text(request.text)

        # Collect missing information & missing task durations
        missing_questions = list(extracted.missing_information)
        for task in extracted.tasks:
            if task.duration_minutes is None:
                q = f"How many minutes does task '{task.name}' take?"
                if q not in missing_questions:
                    missing_questions.append(q)

        if missing_questions:
            return SolveResponse(
                status="NEEDS_INPUT",
                message="More information is required before optimization.",
                questions=missing_questions,
                tasks=extracted.tasks,
            )

        return SolveResponse(
            status="EXTRACTED",
            problem_title=extracted.problem_title,
            objective=extracted.objective,
            tasks=extracted.tasks,
            missing_information=extracted.missing_information,
            ambiguities=extracted.ambiguities,
            assumptions=extracted.assumptions,
            extraction_confidence=extracted.extraction_confidence,
        )

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

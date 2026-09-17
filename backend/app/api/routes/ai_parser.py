"""Authenticated preview and explicit confirmation. No provider calls in routes."""
from typing import Annotated
from fastapi import APIRouter, Depends
from app.dependencies.ownership import CurrentUser, Database, get_owned_plan
from app.schemas.ai_parser import ParsePlanRequest, ParsePlanResponse, ConfirmPlanRequest, ConfirmPlanResponse
from app.services.ai.gemini_client import GeminiClient, get_gemini_client
from app.services.ai.planning_parser import parse_plan, confirm_plan
from app.services.memory_engine import route_context

router = APIRouter(prefix="/api/ai", tags=["AI planning input"])


@router.post("/parse-plan", response_model=ParsePlanResponse)
def preview_plan(payload: ParsePlanRequest, user: CurrentUser, db: Database,
                 gemini: Annotated[GeminiClient, Depends(get_gemini_client)]):
    if payload.existing_plan_id is not None:
        get_owned_plan(payload.existing_plan_id, db, user)
    result = parse_plan(gemini, payload.text)
    # Context stays separate and local. It is neither sent to Gemini nor applied.
    if payload.include_context and user.memory_enabled:
        result.suggested_context = route_context(db, payload.existing_plan_id, user)
    return result


@router.post("/confirm-plan", response_model=ConfirmPlanResponse, status_code=201)
def create_confirmed_plan(payload: ConfirmPlanRequest, user: CurrentUser, db: Database):
    return confirm_plan(db, user, payload)

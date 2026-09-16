"""Resolve owned plans once; all nested lookups are scoped to that plan."""
from typing import Annotated

from fastapi import Depends, HTTPException, Path
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import Plan, User
from app.models.planning import utcnow

Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PathID = Annotated[int, Path(gt=0, le=2**31 - 1)]


def get_owned_plan(plan_id: PathID, db: Database, user: CurrentUser) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.user_id == user.id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


OwnedPlan = Annotated[Plan, Depends(get_owned_plan)]


def get_writable_plan(plan: OwnedPlan, db: Database) -> Plan:
    # A row UPDATE acquires the transaction's write lock before reading relationships.
    # SQLite serializes writers; other relational engines lock this plan's row.
    # Concurrent graph edits therefore validate against the previous committed edit.
    result = db.execute(update(Plan).where(Plan.id == plan.id).values(updated_at=utcnow()))
    if result.rowcount != 1:
        raise HTTPException(status_code=404, detail="Plan not found")
    # Ownership was read before the lock: reload fields to avoid stale PATCH merges.
    db.refresh(plan)
    return plan


WritablePlan = Annotated[Plan, Depends(get_writable_plan)]


def get_nested(db: Session, model, entity_id: int, **scope):
    entity = db.scalar(select(model).filter_by(id=entity_id, **scope))
    if entity is None:
        raise HTTPException(status_code=404, detail="Requested planning record not found")
    return entity

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, get_token_service
from app.models import User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.security import TokenService, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])
Database = Annotated[Session, Depends(get_db)]


def find_user(db: Session, email: str) -> User | None:
    # Supports pre-existing mixed-case email rows without changing the schema.
    return db.scalar(select(User).where(func.lower(User.email) == email))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Database) -> User:
    duplicate = HTTPException(status_code=409, detail="An account with this email already exists")
    if find_user(db, payload.email) is not None:
        raise duplicate
    user = User(
        name=payload.name, email=payload.email,
        password_hash=hash_password(payload.password.get_secret_value()),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # The unique database index also protects simultaneous registrations.
        if find_user(db, payload.email) is not None:
            raise duplicate from None
        raise
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin, response: Response, db: Database,
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenResponse:
    user = find_user(db, payload.email)
    valid = verify_password(payload.password.get_secret_value(), user.password_hash if user else None)
    if user is None or not valid:
        raise HTTPException(
            status_code=401, detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=tokens.issue(user.id), expires_in=tokens.expires_in)


@router.get("/me", response_model=UserResponse)
def current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user

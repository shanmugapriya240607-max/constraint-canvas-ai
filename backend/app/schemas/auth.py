"""Public authentication contracts; credentials are never response fields."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator
from app.schemas.common import ORMModel


class EmailInput(BaseModel):
    email: EmailStr = Field(max_length=320)

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Account identifiers are intentionally case-insensitive, including local parts.
        return value.lower()


class UserRegister(EmailInput):
    name: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=8, max_length=1024)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class UserLogin(EmailInput):
    password: SecretStr = Field(min_length=1, max_length=1024)


class UserResponse(ORMModel):
    id: int
    name: str
    email: str
    memory_enabled: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        # SQLite reads UTC timestamps without their timezone information.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int

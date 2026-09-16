"""Environment-based settings; importing this module does not create database files."""
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "ConstraintCanvas AI"
APP_VERSION = "2.0.0"
SERVICE_NAME = f"{APP_NAME} Backend"
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'data' / 'constraint_canvas.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        hide_input_in_errors=True,
        extra="ignore",
    )

    database_url: str = DEFAULT_DATABASE_URL
    gemini_api_key: SecretStr | None = None
    app_env: Literal["development", "production"] = "development"
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=1440)
    frontend_origins: Annotated[list[str], NoDecode] = [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in (3000, 5173, 5174, 4173)
    ]

    @field_validator("database_url", mode="before")
    @classmethod
    def default_database_if_blank(cls, value: str) -> str:
        return value.strip() or DEFAULT_DATABASE_URL

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if self.jwt_secret_key is not None:
            secret = self.jwt_secret_key.get_secret_value()
            if len(secret.encode("utf-8")) < 32 or not secret.strip():
                raise ValueError("JWT_SECRET_KEY must contain at least 32 bytes")
        elif self.app_env == "production":
            raise ValueError("JWT_SECRET_KEY is required in production")
        return self

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        origins = value.split(",") if isinstance(value, str) else value
        cleaned = []
        for origin in origins:
            origin = origin.strip().rstrip("/")
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.path or parsed.query or parsed.fragment
                or parsed.username or parsed.password
            ):
                raise ValueError("FRONTEND_ORIGINS must contain comma-separated HTTP(S) origins")
            cleaned.append(origin)
        return cleaned


settings = Settings()

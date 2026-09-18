import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, DEFAULT_DATABASE_URL, Settings
from app.database import build_engine


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("DATABASE_URL", "GEMINI_API_KEY", "FRONTEND_ORIGINS", "APP_ENV", "JWT_SECRET_KEY", "JWT_ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES"):
        monkeypatch.delenv(name, raising=False)


def test_empty_environment_uses_safe_defaults(monkeypatch):
    for name in ("DATABASE_URL", "GEMINI_API_KEY", "FRONTEND_ORIGINS", "APP_ENV", "JWT_SECRET_KEY", "JWT_ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES"):
        monkeypatch.setenv(name, "")
    config = Settings(_env_file=None)
    assert config.database_url == DEFAULT_DATABASE_URL
    assert config.gemini_api_key is None
    assert "http://localhost:5173" in config.frontend_origins
    assert "http://127.0.0.1:3000" in config.frontend_origins


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:///file.db\nGEMINI_API_KEY=\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://localhost:5173, http://localhost:3000/")
    config = Settings(_env_file=env_file)
    assert config.database_url == "sqlite:///:memory:"
    assert config.frontend_origins == ["http://localhost:5173", "http://localhost:3000"]
    assert config.gemini_api_key is None


def test_wildcard_cors_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, frontend_origins="*")


def test_relative_sqlite_path_is_backend_relative():
    engine = build_engine("sqlite:///./data/example.db")
    try:
        assert engine.url.database == str((BACKEND_DIR / "data/example.db").resolve())
    finally:
        engine.dispose()


def test_production_requires_jwt_secret():
    with pytest.raises(ValidationError, match="required in production"):
        Settings(_env_file=None, app_env="production")


@pytest.mark.parametrize("secret", ["too-small", " " * 40])
def test_weak_jwt_secret_rejected(secret):
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(_env_file=None, jwt_secret_key=secret)


@pytest.mark.parametrize("minutes", [0, -1, 1441])
def test_token_lifetime_validated(minutes):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, access_token_expire_minutes=minutes)


def test_jwt_algorithm_is_allowlisted():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_algorithm="none")


def test_environment_jwt_configuration(monkeypatch, tmp_path):
    import secrets
    from app.services.security import TokenService

    secret = secrets.token_urlsafe(48)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_ORIGINS", "https://frontend.example.com")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'production.db').as_posix()}")
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    config = Settings(_env_file=None)
    assert config.jwt_secret_key.get_secret_value() == secret
    assert secret not in repr(config)
    first = TokenService(config)
    second = TokenService(config)
    assert first.expires_in == 900
    assert second.subject(first.issue(1)) == 1


def test_development_keys_are_ephemeral():
    from jwt.exceptions import InvalidTokenError
    from app.services.security import TokenService

    config = Settings(_env_file=None)
    first, second = TokenService(config), TokenService(config)
    with pytest.raises(InvalidTokenError):
        second.subject(first.issue(1))


def test_configuration_errors_hide_secret_input():
    secret = "private-invalid-config-key"
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, jwt_secret_key=secret)
    assert secret not in str(error.value)

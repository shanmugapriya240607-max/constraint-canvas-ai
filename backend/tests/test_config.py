import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, DEFAULT_DATABASE_URL, Settings
from app.database import build_engine


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("DATABASE_URL", "GEMINI_API_KEY", "FRONTEND_ORIGINS"):
        monkeypatch.delenv(name, raising=False)


def test_empty_environment_uses_safe_defaults(monkeypatch):
    for name in ("DATABASE_URL", "GEMINI_API_KEY", "FRONTEND_ORIGINS"):
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

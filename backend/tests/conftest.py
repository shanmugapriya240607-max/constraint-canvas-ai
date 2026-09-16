import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import build_engine
from app.main import create_app


@pytest.fixture
def db_engine(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    yield engine
    engine.dispose()


@pytest.fixture
def application(db_engine):
    config = Settings(_env_file=None, frontend_origins=["http://localhost:5173"])
    return create_app(config=config, db_engine=db_engine)


@pytest.fixture
def client(application):
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client

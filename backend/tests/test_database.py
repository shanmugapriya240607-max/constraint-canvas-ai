import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.database import Base, build_engine, init_db
from app.main import create_app
from app.models import User


def test_lifespan_initializes_database(client, db_engine):
    inspector = inspect(db_engine)
    assert set(inspector.get_table_names()) == set(Base.metadata.tables)
    assert set(Base.metadata.tables) == {"users", "plans", "resources", "resource_availability", "tasks", "task_requirements", "task_dependencies", "constraint_rules", "solver_runs"}
    assert {column["name"] for column in inspector.get_columns("users")} == {
        "id", "name", "email", "password_hash", "memory_enabled", "created_at",
    }
    assert any(
        index["column_names"] == ["email"] and index["unique"]
        for index in inspector.get_indexes("users")
    )


def test_user_defaults_and_unique_email(client, db_engine):
    with Session(db_engine) as db:
        user = User(name="Expo User", email="user@example.test", password_hash="test-hash")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None
        assert user.memory_enabled is False
        assert user.created_at is not None
        db.add(User(name="Duplicate", email=user.email, password_hash="another-hash"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_initialization_preserves_data_and_other_tables(db_engine):
    init_db(db_engine)
    with Session(db_engine) as db:
        db.add(User(name="Existing", email="existing@example.test", password_hash="hash"))
        db.commit()
    with db_engine.begin() as connection:
        connection.execute(text("CREATE TABLE prototype_data (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO prototype_data (id) VALUES (1)"))
    init_db(db_engine)
    with Session(db_engine) as db:
        assert db.scalar(select(User)).name == "Existing"
        assert db.execute(text("SELECT id FROM prototype_data")).scalar_one() == 1


def test_sqlite_foreign_keys_enabled(db_engine):
    with db_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_engine_construction_does_not_create_database(tmp_path):
    path = tmp_path / "new-directory" / "new.db"
    engine = build_engine(f"sqlite:///{path.as_posix()}")
    try:
        assert not path.parent.exists()
        init_db(engine)
        assert path.exists()
    finally:
        engine.dispose()


def test_in_memory_database_shared_with_request_threads():
    engine = build_engine("sqlite:///:memory:")
    with TestClient(create_app(db_engine=engine)) as client:
        assert client.get("/api/health").json()["database"] == "connected"
        assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)


def test_failed_initialization_stops_startup(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path.as_posix()}")
    with pytest.raises(OperationalError):
        with TestClient(create_app(db_engine=engine)):
            pytest.fail("Startup should not succeed with an invalid database path")


def test_app_factory_uses_custom_database_url(tmp_path):
    from app.config import Settings

    path = tmp_path / "custom.db"
    config = Settings(_env_file=None, database_url=f"sqlite:///{path.as_posix()}")
    with TestClient(create_app(config=config)) as client:
        assert client.get("/api/health").status_code == 200
        assert path.exists()

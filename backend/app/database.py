"""SQLAlchemy engine, session dependency, and explicit schema initialization."""
from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import BACKEND_DIR, settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    options = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if url.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool
        elif not Path(url.database).is_absolute():
            url = url.set(database=str((BACKEND_DIR / url.database).resolve()))
    db_engine = create_engine(url, **options)
    if url.get_backend_name() == "sqlite":
        @event.listens_for(db_engine, "connect")
        def configure_sqlite(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return db_engine


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(db_engine: Engine = engine) -> None:
    # Register tables before creating metadata; never drop or migrate existing data.
    from app.models import User  # noqa: F401

    if db_engine.dialect.name == "sqlite":
        database = db_engine.url.database
        if database and database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=db_engine)


def get_db(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session

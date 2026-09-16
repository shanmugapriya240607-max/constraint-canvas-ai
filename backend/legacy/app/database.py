import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker

# Derive directory path relative to this database.py file
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_FILE = DATA_DIR / "constraint_canvas.db"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or DATABASE_URL.strip() == "":
    DATABASE_URL = DEFAULT_DB_URL

# For SQLite, check_same_thread=False is required for FastAPI multithreaded requests
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SolveRun(Base):
    __tablename__ = "solve_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_text = Column(Text, nullable=False)
    problem_title = Column(String(255), nullable=True)
    objective = Column(Text, nullable=True)
    extracted_json = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    result_json = Column(Text, nullable=True)
    error_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)


def init_db(custom_engine=None):
    target_engine = custom_engine or engine
    Base.metadata.create_all(bind=target_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

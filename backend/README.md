# ConstraintCanvas AI Backend — Phase 1

Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, and pytest.
Only API foundation is active. No scheduling, AI parsing, authentication,
planning memory, or optimization is implemented. No paid API is called.

## Local setup (PowerShell, from the repository root)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only if you do not already have a .env:
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

On macOS/Linux use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`.
Open http://127.0.0.1:8000/docs for OpenAPI documentation.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/api/health
.\.venv\Scripts\python.exe -m pytest
```

## Configuration

Environment variables override backend/.env. Blank values use defaults.
- DATABASE_URL: defaults to backend/data/constraint_canvas.db. Relative SQLite
  paths are always anchored to backend/. In-memory SQLite is supported for tests.
- GEMINI_API_KEY: optional secret, reserved for later phases and never used here.
- FRONTEND_ORIGINS: comma-separated HTTP(S) origins, for example
  `http://localhost:5173,http://127.0.0.1:3000`. Defaults include localhost and
  127.0.0.1 on ports 3000, 5173, 5174, and 4173. No wildcard origin is allowed.
  The prototype's singular FRONTEND_ORIGIN setting is no longer used.

.env and database files are already ignored by the repository .gitignore.

## Architecture and behavior

- app/config.py: typed environment settings and API identity.
- app/database.py: Base, engine, SessionLocal, get_db, and explicit init_db.
- app/models/: only User is registered, with a unique indexed email, stored
  password hash, opt-in memory flag (false), and UTC creation timestamp.
  SQLite returns naive datetimes on reads; stored creation times represent UTC.
- app/schemas/: reusable response models and Pydantic v2 ORM base.
- app/api/routes/: GET /api/health runs SELECT 1. Connectivity failure returns
  HTTP 503 with status=error and database=disconnected; success returns HTTP 200.
- app/main.py: app factory, lifespan, root endpoint, CORS, and a generic JSON
  HTTP 500 handler. Exception details stay in server logs. FastAPI retains its
  standard HTTP and request-validation handlers.
- app/services/: reserved package, no later-phase services implemented.
- tests/: isolated temporary databases, real HTTP test clients, no external APIs.
- legacy/: original prototype code and tests, archived outside active execution.

Table creation happens during lifespan startup, not module import. Startup fails
if initialization fails. create_all is only local schema bootstrapping, not a
migration system: it does not alter or drop existing tables. Existing prototype
solve_runs data is preserved but is not mapped or exposed by the active app.
Add migrations when schema evolution is needed in a later phase.

The old /api/solve and /api/history endpoints are intentionally absent. The
frontend has not been changed; it must be integrated in a later phase.

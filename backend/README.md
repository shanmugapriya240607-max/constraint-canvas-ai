# ConstraintCanvas AI Backend — Foundation and Authentication

Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, and pytest.
Phase 1 foundation and Phase 2 authentication are active. No scheduling, planning,
AI parsing, memory behavior, or optimization is implemented. No paid API is called.

## Local setup (PowerShell, from the repository root)

```powershell
cd backend
# Create only if no virtual environment exists:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Copy only if you do not already have .env:
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

On macOS/Linux use `.venv/bin/python` instead. Open http://127.0.0.1:8000/docs.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/api/health
.\.venv\Scripts\python.exe -m pytest
```

## Configuration

Environment variables override backend/.env; blank values use defaults.
- DATABASE_URL: defaults to backend/data/constraint_canvas.db. Relative SQLite
  paths resolve against backend/. In-memory SQLite is supported for tests.
- GEMINI_API_KEY: optional, reserved, not used.
- FRONTEND_ORIGINS: comma-separated HTTP(S) origins. Defaults include localhost
  and 127.0.0.1 on ports 3000, 5173, 5174, and 4173; wildcard origins are rejected.
- APP_ENV: development (default) or production.
- JWT_SECRET_KEY: supply a randomly generated secret of at least 32 bytes.
  Production refuses to start without one. Development without a key uses a
  random per-app key and logs a warning: tokens become invalid after restart or
  reload. Set a stable secret when using multiple workers. No fixed fallback
  secret is embedded in source. Generate locally with:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- JWT_ALGORITHM: HS256 only; the verification algorithm is never taken from a token.
- ACCESS_TOKEN_EXPIRE_MINUTES: defaults to 60, allowed range 1–1440.

Store generated secrets in environment variables or the ignored backend/.env.
.env and SQLite files are already ignored by Git. Never commit real credentials.

## Authentication API

All bodies are JSON, including login; no OAuth2 form/multipart dependency is needed.

- POST /api/auth/register: name, email, password. Returns 201 with id, name, email,
  memory_enabled, and created_at. Duplicate email returns 409. Invalid fields
  return 422. Names are trimmed and 1–100 characters; passwords are 8–1024
  characters and never trimmed. Email addresses are validated, trimmed, and
  lowercased in full as a deliberate case-insensitive account identifier policy.
- POST /api/auth/login: email, password. Returns access_token, token_type=bearer,
  and expires_in (seconds). Unknown accounts and wrong passwords both return
  401 with `Invalid email or password`. Token responses disable caching.
- GET /api/auth/me: requires `Authorization: Bearer <access_token>` and returns
  the same public user fields as registration. Missing, invalid, expired tokens,
  or tokens referencing missing users return 401 with a Bearer challenge.

In Swagger, register or log in with Try it out, copy the access_token, then use
Authorize and paste the token. Call /api/auth/me with that authorization.

Passwords are stored only as randomly salted Argon2id hashes via pwdlib.
Unknown-account login still performs password verification to reduce timing
leaks. Responses use an explicit UserResponse allowlist, excluding password_hash.
Validation errors omit input/context so submitted passwords are never echoed.
SQLAlchemy hides bound parameters in exceptions. Passwords, keys, and tokens
are not logged by authentication code.

JWTs contain only sub (string user ID), iat, and exp. Signature, algorithm, required
claims, timestamps, valid ID range, and current database user existence are checked.
Access tokens expire; refresh, logout/revocation, password reset, email verification,
and login rate limiting are not part of this phase. Use HTTPS for deployment and
apply request throttling at the deployment boundary before public exposure.

## Architecture and database compatibility

- app/config.py: validated environment settings and unchanged API identity.
- app/database.py: Base, engine, SessionLocal, get_db, explicit init_db.
- app/models/db_models.py: existing User table, unchanged columns and constraints.
- app/schemas/auth.py: registration/login inputs and public user/token responses.
- app/services/security.py: password hashing and JWT issuing/validation.
- app/dependencies/auth.py: reusable get_current_user dependency and HTTP bearer.
- app/api/routes/auth.py: registration, login, current user.
- app/api/routes/health.py: actual SELECT 1 probe, HTTP 200 on success, 503 on failure.
- app/main.py: app factory, lifespan, CORS, root, exception and validation handlers.
- tests/: all foundation and authentication tests use isolated temporary databases.
- legacy/: unchanged reference archive of the original prototype; not executable
  with current imports and excluded from active pytest collection.

No schema migration is needed. Existing SQLite data remains usable; legacy
solve_runs data remains preserved but unmapped. Existing mixed-case ASCII email
rows are found case-insensitively. Existing accounts require a valid Argon2 hash
to log in; placeholder prototype hashes are safely rejected. memory_enabled
remains false by default; no memory behavior is implemented. SQLite creation
values represent UTC; public user responses explicitly include the UTC offset.

Schema creation occurs at lifespan startup, never on import, and initialization
failure stops startup. create_all does not alter or drop existing tables and is
not a migration system. Add migrations when later schema changes require them.
The old /api/solve and /api/history endpoints remain absent. The frontend is unchanged.

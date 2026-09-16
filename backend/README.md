# ConstraintCanvas AI Backend — Foundation, Authentication, and Planning Data

Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, and pytest.
Phases 1–3 provide foundation, authentication, and planning data CRUD. No scheduling,
AI parsing, memory behavior, allocation, or optimization is implemented. No paid API is called.

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
- tests/: all foundation, authentication, and planning tests use isolated temporary databases.
- legacy/: unchanged reference archive of the original prototype; not executable
  with current imports and excluded from active pytest collection.

The new planning tables are additive: startup creates them without altering users. Existing SQLite data remains usable; legacy
solve_runs data remains preserved but unmapped. Existing mixed-case ASCII email
rows are found case-insensitively. Existing accounts require a valid Argon2 hash
to log in; placeholder prototype hashes are safely rejected. memory_enabled
remains false by default; no memory behavior is implemented. SQLite creation
values represent UTC; public user responses explicitly include the UTC offset.

Schema creation occurs at lifespan startup, never on import, and initialization
failure stops startup. create_all does not alter or drop existing tables and is
not a migration system. Add migrations when later schema changes require them.
The old /api/solve and /api/history endpoints remain absent. The frontend is unchanged.

## Phase 3 planning data API

Every operation requires the Phase 2 Bearer token. Plans are owned by the authenticated
user, never by a supplied user_id. Cross-user and mismatched nested IDs return 404.
Input schemas reject unknown fields. Success is 201 for POST, 200 for GET/PATCH,
and an empty 204 for DELETE. Collections are JSON arrays ordered by ID; availability
is ordered by start time and ID. Reads expose explicit response models only.

| Collection path | Collection methods | Item methods |
| --- | --- | --- |
| /api/plans | POST, GET | GET, PATCH, DELETE /{plan_id} |
| /api/plans/{plan_id}/resources | POST, GET | GET, PATCH, DELETE /{resource_id} |
| /api/plans/{plan_id}/resources/{resource_id}/availability | POST, GET | PATCH, DELETE /{availability_id} |
| /api/plans/{plan_id}/tasks | POST, GET | GET, PATCH, DELETE /{task_id} |
| /api/plans/{plan_id}/tasks/{task_id}/requirements | POST, GET | DELETE /{requirement_id} |
| /api/plans/{plan_id}/dependencies | POST, GET | DELETE /{dependency_id} |
| /api/plans/{plan_id}/constraints | POST, GET | PATCH, DELETE /{constraint_id} |

GET /api/plans/{plan_id}/full returns plan, resources with availability, tasks with
requirements, dependencies, and constraints. It does not contain any solver result.
The implementation batches nested reads instead of querying separately per item.
Swagger /docs documents all 30 planning operations and their static Pydantic v2 schemas.

### Time and duration contract

Use full ISO 8601 datetimes with an explicit timezone, e.g. `2026-09-16T09:00:00+05:30`.
Naive datetimes are rejected. All planning timestamps are stored in UTC and returned
as aware UTC timestamps. Planning windows and availability require end > start.
A task's deadline must be later than earliest_start when both are present.
PATCH validates the merged persisted state, not just the submitted fields.

Task creation accepts exactly one of:

```json
{"name":"Development","duration_value":3,"duration_unit":"hours","priority":"high"}
```

```json
{"name":"Testing","duration_minutes":90,"priority":"critical"}
```

- duration_minutes is an explicit positive integer canonical value.
- duration_value must be accompanied by duration_unit: seconds, minutes, or hours.
- Convenient values are positive finite decimals with up to 9 fractional places
  and 20 total digits. Normalized minutes must fit 1 through 2,147,483,647.
- Conversion uses exact rational arithmetic and rounds fractional minutes UP
  (ceiling), preserving required duration for future integer scheduling.
- 2 hours -> 120; 1800 seconds -> 30; 61 seconds -> 2; 0.01 minutes -> 1.
- Only duration_minutes is persisted or returned; no missing unit is guessed.
- A PATCH that changes convenient duration must supply both value and unit.

Creation defaults: plan status=draft, task priority=medium, resource active=true,
constraint hardness=hard/source=manual/enabled=true. Plan statuses may be edited to
draft, ready, solved, infeasible, or archived, but are only stored labels in this
phase: no solving or feasibility checks occur. Optional task dates/descriptions
and resource cost can be cleared with null; required properties cannot.

### Resources, requirements, dependencies, and constraints

Resource names are trimmed and Unicode case-folded for per-plan uniqueness (409 on
conflict). The internal name_key is not returned. Types are trimmed and case-folded;
capacities and requirement quantities are positive integers. Costs are optional,
nonnegative fixed decimals with at most 14 digits/4 decimal places. Decimal costs
are returned as JSON strings to preserve precision.

A specific resource requirement must reference a resource in the same plan with a
matching type. A referenced resource cannot be deleted or have its type changed
until its specific requirements are removed (409). Availability belongs to one
resource; deleting an unreferenced resource cascades its availability.

Dependencies use before_task_id -> after_task_id. Self-links and cycles return 400;
duplicates return 409; missing/out-of-plan references return 404. Cycle validation
performs deterministic iterative graph reachability: adding A -> B is rejected
if B already reaches A. All nested writes acquire the plan's transaction write
lock before reading relationships, so concurrent edge additions cannot jointly
create a cycle. This is graph validation only, with no OR-Tools dependency.

Constraint types are deadline, dependency, resource_capacity, availability,
max_work_hours, preferred_resource, preferred_time, and custom. Hardness is hard or
soft; source is manual, ai, memory, or system. These are metadata labels, not feature
implementations. Soft rules require positive finite weight (default 1 when omitted);
hard rules may omit weight. Explicit null weight on a soft rule is rejected.
Changing hard -> soft without weight assigns 1 if there was no previous weight.

Parameters must be a JSON object containing only finite JSON values, capped at
64 KiB when serialized. Custom strings, including strings resembling code, are
stored as inert data; no eval, exec, template evaluation, or rule interpretation.
PATCH replaces the parameters object, rather than recursively merging it. Embedded
IDs in generic parameters are not interpreted or treated as database references.

The API does not reject overlapping availability, out-of-plan time windows, excess
resource demand, or task durations that cannot fit a window; those are later
feasibility questions, not CRUD rules. No allocation or scheduling happens here.

### Integrity and verification

New models live in app/models/planning.py: Plan, Resource, ResourceAvailability,
Task, TaskRequirement, TaskDependency, ConstraintRule. Foreign keys, indexes,
uniqueness, and check constraints protect the database. Composite foreign keys
ensure dependencies and specific requirements cannot cross plan boundaries.
Deleting a plan cascades all seven categories of planning data; deleting a task
cascades its requirements and incoming/outgoing dependencies. Authentication tables
and existing local database records are retained. No migration of existing tables
or new package dependency is required.

Ownership helpers live in app/dependencies/ownership.py; CRUD is in
app/api/routes/plans.py; static schemas are in app/schemas/planning.py; persistence,
graph validation, and full-plan assembly are in app/services/planning.py.

Run the full test suite with the existing environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

For the repeatable requested manual scenario, start a server on port 8002 from
backend/ using the same environment/database settings, then run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002
# In another terminal, from backend/:
.\.venv\Scripts\python.exe scripts/verify_planning.py
```

This creates a fresh local verification user and College Fest Website plan, all
three resources, two availability windows, three tasks, two requirements, one
dependency, and a soft preferred-time constraint. It verifies authentication,
health, Swagger, the complete response, and stored database relationships. It
preserves existing records, prints no credentials, and saves a real response to
examples/college_fest_plan.json. Its extra verification account/plan are intentional
local demo data, not fixtures or preloaded production data.

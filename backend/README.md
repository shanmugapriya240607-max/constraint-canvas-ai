# ConstraintCanvas AI Backend — Foundation, Planning, and CP-SAT

Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, and pytest.
Phases 1–4 provide foundation, authentication, planning CRUD, and real OR-Tools CP-SAT
scheduling/allocation. No Gemini, parsing, planning memory, recovery, or Phase 5 features
are implemented. No paid API is called.

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
create a cycle. CRUD graph validation remains independent of the solver.

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
and existing local database records are retained. Phase 3 did not require a migration of existing tables; Phase 4 adds a new history table and OR-Tools dependency.

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

## Phase 4: real OR-Tools optimization

The official `ortools==9.12.4544` package is pinned for repeatable Python 3.12+
installations (verified here on the existing Python 3.13 environment). There is no
LLM, dummy schedule, random scoring, or arbitrary code execution. The active
implementation is separate from the untouched legacy prototype.

### Routes and architecture

- POST /api/plans/{plan_id}/solve accepts an optional JSON body:
  `{"max_solve_seconds":10}`. Default 10, positive, maximum 30 seconds; invalid
  limits return 422. It returns optimal, feasible, infeasible, or unknown.
- GET /api/plans/{plan_id}/runs returns newest-first run summaries.
- GET /api/plans/{plan_id}/runs/{run_id} returns a summary plus its stored result.

All three require JWT ownership and return 404 for another user's plan/run.
The complete API now contains 38 application operations, excluding Swagger routes.

app/services/solver/ contains:
- input_builder.py: detached snapshot validation, safe rule parsing, integer times.
- cp_sat_solver.py: mandatory task intervals, allocation variables, CP-SAT solve.
- objective.py: bounded integer objective with strict makespan precedence.
- result_builder.py: actual CP-SAT values and ISO timestamp responses.
- service.py: snapshot, solve, status update, and atomic persistence.

app/schemas/solver.py defines response models and static allowlisted rule-parameter
schemas. app/api/routes/solver.py contains only API orchestration. SolverRun is in
app/models/solver.py; the new solver_runs table is additive. Old prototype
solve_runs data and existing users/plans are not altered or migrated.

### Hard time, resource, and availability semantics

Time variables are integer minute offsets from the exact planning_start timestamp.
Task intervals obey end = start + duration. Every task stays in the planning window;
each dependency enforces start(after) >= end(before). Explicit task deadlines are
hard. Earliest starts round UP to the next offset minute; deadlines, availability
ends, and the planning horizon round DOWN. Datetime arithmetic uses integer
microseconds, never floating-point solver time. Responses include offsets and ISO UTC.

Generic requirements match trimmed/case-folded types and allocate exactly the
required number of units across compatible active resources. Specific requirements
allocate only the named active resource. Multiple requirements are additive; a unit
cannot satisfy two distinct requirements at the same time. Assignment is fixed for
the entire non-preemptive task, with no mid-task resource swapping.

Per-requirement/resource integer unit variables sum to required quantity. Their
per-task/resource totals are the demands of optional intervals in AddCumulative.
Each resource's cumulative constraint enforces simultaneous demand <= its capacity
inside CP-SAT, rather than repairing an invalid result afterward.

Each used resource/task pair selects exactly ONE recorded availability window in
which the entire interval fits. Gaps cannot be crossed and overlapping windows are
not merged to create a longer window. With no records, a resource is available for
the entire plan. Existing windows outside the plan do NOT trigger that fallback.
Hard availability rules intersect the recorded windows (or the whole-plan default).

The solver supports 1–50 tasks, up to 30 resources, 200 requirements, 100 rules,
100 windows/resource, a horizon of 1–44640 minutes, and capacities/quantities up to
1000. Larger inputs return 422 before model construction.

### Explicit constraint rule contracts

Only enabled rules are applied. Parameters reject unknown properties and use
strict positive IDs and timezone-aware datetimes. All references must be in-plan.

| Hard type | Required parameter object | Meaning |
| --- | --- | --- |
| deadline | task_id, deadline | Additional hard task completion bound |
| dependency | before_task_id, after_task_id | Additional precedence edge |
| resource_capacity | resource_id, capacity | Nonnegative cap; can tighten, never raise stored capacity |
| availability | resource_id, available_from, available_until | Additional restriction intersected with existing windows |
| max_work_hours | resource_id, max_hours | Whole-plan total unit-hours budget; duration × assigned units |

For max_work_hours, max_hours is positive (up to 6 fractional digits) and converted
to a conservative integer minute budget by rounding down. This is total unit-work
across the entire plan, not an elapsed-span or per-day limit.

Supported soft types:
- preferred_resource: `{task_id, resource_id}`. Penalty 1 if the named resource is
  not used by that task, otherwise 0. This never creates a new requirement and an
  inactive/incompatible preferred resource can remain unsatisfied.
- preferred_time: `{task_id, preferred_before}`. Penalty is completion lateness in
  minutes. The preferred offset is floored and clamped to [0, horizon]; values
  outside the plan therefore cannot create oversized objective constants.

Stored soft weights must be positive and at most 1000 for these handlers. They are
scaled by 1000, rounded half-up, with minimum scaled weight 1. Unsupported soft
rules are reported in warnings. Unsupported enabled HARD rules (including custom)
return 422. Disabled rules are ignored. Custom JSON/code is never interpreted.

### Exact objective and determinism

Let H be the planning horizon, M the maximum task end, p_i the priority weight
(low=1, medium=2, high=4, critical=8), and e_i each task end offset.
Let P = sum(p_i * e_i). For each supported soft rule j, w_j is its scaled weight,
f_j its penalty, and U_j its penalty upper bound (1 for preferred_resource; H for
preferred_time). Define:

```
S = sum(w_j * f_j)
B = 1000 * H * sum(p_i) + sum(w_j * U_j)
minimize (B + 1) * M + 1000 * P + S
```

Because 0 <= 1000P + S <= B, a one-minute makespan improvement dominates every
secondary term. Priorities encourage early completion, never impose hard ordering.
The maximum expression is checked below 2^60 to avoid int64 overflow. Optional idle
time heuristics and cost objectives are not added. Responses report M, P, and S.

CP-SAT uses one search worker, random_seed=0, sorted IDs/edges, and a pinned version.
Identical inputs normally yield identical schedules. Wall-clock cutoffs or different
platforms/library versions can still affect which incumbent/tied optimum is returned.
An incumbent without an optimality proof is feasible, never labelled optimal.
UNKNOWN returns an empty schedule and a warning, never falsely claims infeasibility.

### Validation versus infeasibility

422 means malformed/unsupported input: no tasks, missing/inactive/wrong-type specific
resources, no active generic match, cross-plan references, dependency cycles,
unsupported hard rules, invalid parameters, duration exceeding the whole horizon,
or a deadline before planning_start. No run/status change is committed for these.

Well-formed but unsatisfiable combinations return HTTP 200 with status=infeasible
and an empty schedule. Examples: duration cannot meet a within-plan deadline,
a specific resource has no fitting window, or three simultaneous units are required
while only two compatible units exist. The capacity-shortage case follows the
explicit requested infeasible demo policy; CP-SAT proves the contradiction through
its allocation equalities. No recovery suggestions or detailed conflict analysis.

### History, status, and concurrency

Every completed CP-SAT attempt (including unknown) appends a SolverRun with status,
makespan, wall time, version, the full result JSON, input snapshot, and UTC timestamp.
The result JSON contains the schedule, objective, metrics, and warnings. Old runs
are never overwritten by re-solving or editing/deleting tasks/resources. Deleting
the parent plan explicitly cascades its history.

Optimal/feasible changes plan.status to solved; proven infeasible changes it to
infeasible; unknown leaves the previous status unchanged. Original tasks, resources,
dates, rules, and requirements are never rewritten. Status and run save atomically.
The existing plan write lock is held through solve/persistence to prevent concurrent
input changes. SQLite serializes writers during this bounded demo solve; use a
background queue/concurrency design in a later scaling phase if required.

### Manual verification and the expo example correction

The requested original example is mathematically infeasible: Development takes
180 minutes before Testing can take 90 minutes on Ravi, whose 09:00–13:00 window is
only 240 minutes. The verification script preserves that scenario and confirms
infeasibility. It creates a separately labelled feasible variant extending ONLY
Ravi's window to 13:30; the original records are never modified.

```powershell
# From backend/, in separate terminals:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8003
.\.venv\Scripts\python.exe scripts/verify_solver.py
.\.venv\Scripts\python.exe -m pytest
```

The script verifies real live solves, capacity, timing, dependencies, auth/ownership,
Swagger, plan statuses, and database history. It writes actual responses without
credentials to examples/solver_feasible.json, solver_infeasible.json, and
solver_original_expo.json. It also creates the separate two-unit/three-unit-demand
infeasible scenario. All prior CRUD and authentication tests remain in the suite.

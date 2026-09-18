# Deployment: Vercel frontend + Render backend

Prepared configuration only; nothing has been deployed. Use branch `final-integration`.

## Architecture and limits

Deploy the existing Vite build as a Vercel static SPA and FastAPI as a Render
native Python web service. No serverless backend, Docker rewrite, or new database
adapter is needed. Use **one paid backend instance with a persistent disk** and
one Uvicorn worker. OR-Tools runs in the backend process; allow enough CPU/RAM for
your plans (start with at least 1 CPU/2 GB, then measure). Do not use Render's free
ephemeral filesystem for SQLite. Disk-backed services have restart/deploy downtime
and cannot scale horizontally. This is a modest-traffic expo deployment, not an
HA architecture. A PostgreSQL migration/driver and load testing are separate work.

## Backend settings (Render)

- Repository branch: `final-integration`; root directory: `backend`.
- Runtime: Python. `.python-version` selects Python 3.12 for the existing OR-Tools dependency.
  Do not override it with Render's newer default Python runtime.
- Build: `python -m pip install -r requirements.txt`.
- Start: `python start.py` (binds `0.0.0.0:$PORT`, defaults to 8000, one worker,
  no reload). Render supplies PORT. TLS terminates at the host; never expose the
  internal HTTP port directly. Uvicorn retains its default trusted-proxy policy.
- Health check: `/api/health` (checks the database; deliberately does not call Gemini).
- Add a persistent disk mounted at `/var/data` **before first start**.
- Keep automatic deploys disabled until the initial validation below succeeds.

Set server-side environment variables in Render's dashboard:

| Variable | Value |
| --- | --- |
| APP_ENV | production |
| DATABASE_URL | sqlite:////var/data/constraint_canvas.db |
| FRONTEND_ORIGINS | https://YOUR-FRONTEND.vercel.app (or exact custom HTTPS origin) |
| JWT_SECRET_KEY | Random secret of at least 32 bytes; stable across restarts |
| JWT_ALGORITHM | HS256 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 60 |
| GEMINI_API_KEY | Your existing provider key; secret, backend only |
| GEMINI_MODEL | gemini-3.6-flash (configurable; verify access in your account) |
| GEMINI_TIMEOUT_SECONDS | 30 (allowed 1-120) |

Generate JWT_SECRET_KEY locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`
and paste it directly into the host's secret field. Never copy it into Git, logs,
frontend settings, or a VITE_ variable. A missing Gemini key disables parsing only;
manual planning still works. No live provider request is part of deployment checks.

CORS accepts comma-separated exact origins, not paths or wildcards. Production
rejects localhost/HTTP CORS and implicit, relative, or in-memory SQLite defaults.
Use production frontend origins only; authorize preview URLs explicitly when needed.
DATABASE_URL accepts SQLAlchemy URLs, but this deployment ships/tests SQLite only;
other engines need a driver and compatibility/migration validation.

## Frontend settings (Vercel)

- Import the same repository; production branch: `final-integration`.
- Root directory: `frontend`; framework: Vite; Node.js: 22.x.
- Install: `npm ci`; build: `npm run build`; output: `dist`.
- Set **VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com**, without `/api` or
  a trailing path. This is public build-time configuration; rebuild after changes.
- `vercel.json` rewrites SPA deep links (including `/plans/1/results`) to index.html.
- No Gemini or JWT secret belongs on Vercel. Only VITE_API_BASE_URL is needed.
- If the URL is absent, production code uses same-origin API paths rather than
  localhost. This supports reverse-proxy hosts but does NOT connect Vercel to Render;
  the explicit backend URL is required for this two-host setup.

## Exact rollout steps (after approval to deploy)

1. Create/configure the Render service with the settings above and reserve/copy its
   actual HTTPS URL. Attach its disk. Configure Vercel's project to obtain the exact
   frontend origin. Neither example hostname in this document is a real target.
2. Set the backend secrets, persistent DATABASE_URL, and exact FRONTEND_ORIGINS.
   Set Vercel's VITE_API_BASE_URL to the actual Render URL. Do not reuse local .env.
3. Manually deploy Render. Check `/` and `/api/health` for HTTP 200 and database
   `connected`; confirm startup has no ephemeral-JWT warning.
4. Build/deploy Vercel. Refresh `/login` and a nested plan URL directly. Check browser
   network requests target the HTTPS Render URL and CORS allows the frontend origin.
5. Register/login, create a disposable plan, solve it, and open explanation/results.
   Verify a cross-user request remains blocked. Check Gemini with a single approved
   real prompt only when ready to incur provider usage.
6. Restart the backend once; verify the account/plan persists and an unexpired token
   still works. This verifies the disk and stable JWT secret are actually configured.
7. Set up off-service database backups and a restore drill before retaining real data.
   Use Python's sqlite3 `Connection.backup` against the mounted database (or a stopped
   service), not a raw copy of an actively written file. Download/store backups in
   private durable storage. Back up before releases: startup creates missing tables,
   but there is no migration framework for schema changes. A code rollback does not
   reverse a schema change. Do not rely on the local dev database being uploaded.

## Local verification

From backend: `python -m pytest tests/test_production.py tests/test_config.py tests/test_health.py tests/test_auth.py tests/test_ai_parser.py -q`.
From frontend, set VITE_API_BASE_URL to a public HTTPS test origin, then `npm run build`.
Inspect dist for accidental localhost URLs or secrets. Local Windows checks do not
replace the initial Linux host build and startup verification. Use only fake origins for
configuration checks; an actual deployed backend is required for browser smoke tests.

Official host references: [Render disks](https://render.com/docs/disks),
[Render Python](https://render.com/docs/python-version),
[Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite).

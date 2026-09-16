# ConstraintCanvas AI frontend — F1

An isolated React/Vite frontend with authentication and a protected workspace shell.
Node.js 22.12+ (or 20.19+) is required.

## Run

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Set `VITE_API_BASE_URL` to the existing backend origin (default
`http://127.0.0.1:8000`). Restart Vite after environment changes.
The backend must allow the frontend origin through its CORS configuration.
Only login, register, and current-user authentication endpoints are called.
No backend or database changes are part of this block.

```powershell
npm run build
npm run preview
```

## Routes

- Public: `/login`, `/register`.
- Protected: `/dashboard`, `/plans/new`, `/plans`, `/what-if`, `/memory`, `/settings`.
- Root and unknown routes lead to the dashboard (or login when signed out).
- All workspace routes except Dashboard are explicitly unavailable placeholders.
  Dashboard metrics are unknown, not invented zeroes; no planning APIs are called.

Registration redirects to login with a success message. Login sends JSON,
stores the returned token, and verifies the current user with `/api/auth/me`
before granting access. The original destination is restored after sign-in.

## Session design

Token handling lives in `src/services/session.js`; requests and authentication
live in `services/api.js` and `services/auth.js`. AuthContext owns UI session state.

Tokens use sessionStorage: reloads in the current tab restore the session;
logout clears storage and memory. If storage is unavailable the session is
memory-only. Tokens/passwords are never logged; passwords are not persisted.
JavaScript-accessible storage cannot protect against XSS. A future production
cookie-based design requires backend support and is outside F1.

The server's `/me` response is the authority for the user. JWT claims are never
decoded or trusted. A timer based on `expires_in` and authenticated HTTP 401s
clear the session. The backend still enforces actual expiry and authorization.
Network failures during restoration show a retry screen with protected content
hidden, preserving the token until it expires or the user signs out.

Logout is client-side because the current backend has no revocation endpoint.
There is no refresh token flow.

## Browser tests

```powershell
npx playwright install chromium
npm test
```

Alternatively, use installed Edge on Windows:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm test
```

Tests start an isolated Vite server on 127.0.0.1:5174 and cover desktop/mobile
forms, 401/409/422 errors, session reload/expiry/logout, protected redirects,
network recovery, loading, and placeholder navigation. Backend responses are
mocked at the browser network boundary against the existing API contracts:
these checks do not create users or write to the other agent's database.

The old prototype components and `src/api.js` remain unmodified and unimported
for reference. They are excluded from the active application and production
bundle; they can be removed in a separate cleanup once no longer needed.

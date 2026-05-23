# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BCSSM is a full-stack web application with a Flask (Python) backend and React (TypeScript) frontend. Flask serves both the API and the built React SPA. The database is PostgreSQL (Supabase) with Redis for caching.

## Commands

### Backend

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run Flask dev server (port 8080)
python backend/bcssm_backend/__init__.py

# Run all tests
pytest backend/tests/

# Run a single test file
pytest backend/tests/test_utils.py

# Run a single test
pytest backend/tests/test_utils.py::test_function_name

# Run tests with coverage
pytest backend/tests/ --cov=backend

# Lint
flake8 backend/
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Dev server with HMR (port 5173, proxies API to backend)
npm run dev

# Build for production (outputs to dist/, copied to backend/bcssm_backend/static/ in Docker)
npm run build

# Lint
npm run lint

# Unit tests (Vitest)
npm run test:run

# E2E tests (Playwright)
npm run test:e2e
```

### Docker

```bash
# Build and run with Redis
docker-compose up
```

## Architecture

### Backend

- **App factory:** `backend/bcssm_backend/__init__.py` — `create_app()` configures Flask, SQLAlchemy (connection pooling), Redis cache, CORS, and registers 7 route blueprints via `_setup_routes()`.
- **Config:** `backend/config.py` — three configs: `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`.
- **Business logic:** `backend/bcssm_backend/utils.py` — all database queries and caching logic. Uses `execute_query()` for writes (db.session) and `execute_readonly_query()` for reads (engine.connect(), no session overhead).
- **Routes:** `backend/bcssm_backend/routes/` — thin handlers that call utils and return JSON:
  - `routes.py` — `/`, `/login`, `/duty-teams`, `/users-by-section`, `/user-duty`, `/select-user`, `/get-selected-user`, `/logout`, `/get-users`
  - `users.py` — `/api/auth/validate`
  - `duties.py` — `/api/duties/today`, `/api/duties/schedule`
  - `sections.py` — `/api/users/by-section`, `/api/users/section/<name>`
  - `devos_feedback.py` — `/api/devos-feedback`, `/api/devos-feedback/edit`
  - `admin.py` — `/api/admin/cache/clear`, `/api/admin/cache/status`, `/api/admin/cache/info`
  - `system.py` — `/api/sections`, `/api/health`, React SPA fallback (`/<path>`)
- **Globals:** `backend/globals.py` — shared `cache` (Redis) and `db` (SQLAlchemy) instances imported by both `__init__.py` and `utils.py`.
- **Auth helpers:** `backend/bcssm_backend/auth.py` — `get_username_from_request()` extracts username from JSON body, query param, `X-Current-User` header, or session. `get_user_id_from_request()` resolves to DB user ID.
- **Cache decorator:** `backend/bcssm_backend/cache_utils.py` — `@cached_result(key_fn, ttl, error_ttl)` wraps query functions; supports dynamic keys, SQLAlchemy error fallback with optional error TTL.
- **Exceptions:** `backend/bcssm_backend/exceptions.py` — `BaseError` → `DatabaseError`, `CacheError`, `ValidationError`, `AuthenticationError`, `NotFoundError`.

### Caching Strategy (Redis)

| Data | Cache Key Pattern | TTL |
|------|-------------------|-----|
| Users list | `users:all:list` | 15 min |
| User duty | `user:duty:{name}:day{d}:cycle{c}` | 10 min |
| Today's duties | `duties:today:day{d}:cycle{c}:user{name}` | 30 min |
| Duty schedule | `duties:schedule:14day:{date}` | 2 hours |
| All sections | `sections:all:list` | 1 hour |
| Users by section | `users:section:{section}` | 30 min |
| Sections with users | `sections:with_users:all_v6` | 30 min |
| Feedback dates | `feedback:dates:all` | 2 hours |
| User data | `user:data:{name}` | 30 min |

Each cached function has a corresponding `clear_*_cache()` function. Duty keys include day-of-week and cycle-week (0 or 1, computed by `get_current_cycle_week()` with `@lru_cache`) to account for bi-weekly rotation.

### Database

- PostgreSQL via SQLAlchemy; connection pool: `pool_size=3`, `max_overflow=7`.
- Read queries: `execute_readonly_query()` uses `engine.connect()` — no session overhead.
- Write queries: `execute_query()` uses `db.session.begin()`.

### Frontend

- **Entry:** `frontend/src/main.tsx` → `App.tsx` defines React Router routes.
- **API client:** `frontend/src/api.ts` — `apiCall()` wraps fetch and automatically injects the logged-in username into `X-Current-User` header, query params, and POST body. Use `apiGet()` / `apiPost()` wrappers throughout.
- **Auth:** Username stored in `localStorage` as `currentUser` (also `is_logged_in`, `user_role`, `user_section`, `is_leader`). Validated via `GET /api/auth/validate` on load. Transient network errors do not force logout.
- **Auth guard:** `frontend/src/hooks/useRequireAuth.ts` — redirect hook; use in every protected page.
- **Theme:** `ThemeContext.tsx` + `useTheme.ts` — light/dark toggle; wraps app in `ThemeProvider`.
- **Vite proxy:** Dev server proxies `/api/`, `/get-`, `/select-`, `/devos-`, `/duty-` to the Flask backend on port 8080.

### React Router Pages

| Path | Component | Purpose |
|------|-----------|---------|
| `/` | `Home` | Dashboard: duty info, forms for leaders, bank details |
| `/login` | `Login` | User selection dropdown |
| `/duties` | `DutiesPage` | Today's duties + 14-day schedule (tabbed) |
| `/react/devos-feedback` | `DevoFeedback` | View daily feedback by section |
| `/react/devos-feedback/edit` | `DevoFeedbackEdit` | Edit feedback (leaders only) |
| `/sections` | `Sections` | Users grouped by section with filtering |

### Data Flow

1. User logs in → username stored in `localStorage`
2. All API calls include username (header + query param + body)
3. Backend routes call utils functions → Redis cache or PostgreSQL
4. Flask serves the built React `index.html` for all non-API routes (`GET /<path>`)

## CI/CD

GitHub Actions (`.github/workflows/python-app.yml`) runs on push/PR to `develop` with three parallel jobs:

1. **frontend-unit-tests:** Node 20, `npm run lint`, TypeScript type check, `npm run test:run` (Vitest)
2. **frontend-e2e-tests:** Node 20, install Playwright, run `npx playwright test`
3. **build:** Python 3.10, flake8 lint, pytest with coverage, upload to Codecov (85% target enforced via `codecov.yml`)

Active development happens on `develop`; `main` is production.

## Testing

- **Backend unit tests:** `backend/tests/` — 9 files covering routes, utils, auth, cache, and each route domain.
- **Frontend unit tests:** `frontend/src/__tests__/` — 6 files (Vitest + jsdom + @testing-library/react).
- **Frontend E2E tests:** Playwright; `npm run test:e2e` (API calls mocked). In E2E mode Vite disables its API proxy.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/GlomeCS/BCSSM`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

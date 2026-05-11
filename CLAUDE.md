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
```

### Docker

```bash
# Build and run with Redis
docker-compose up
```

## Architecture

### Backend

- **App factory:** `backend/bcssm_backend/__init__.py` — `create_app()` configures Flask, SQLAlchemy (connection pooling), Redis cache, and registers blueprints. Also defines cache admin routes (`/api/admin/cache/*`).
- **Config:** `backend/config.py` — three configs: `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`.
- **Business logic:** `backend/bcssm_backend/utils.py` — all database queries and caching logic live here. Uses `execute_query()` / `execute_readonly_query()` for session management.
- **Routes:** `backend/bcssm_backend/routes/` — thin handlers that call utils and return JSON. Organized by domain: `routes.py` (login, index), `users.py`, `duties.py`, `sections.py`, `devos_feedback.py`.
- **Globals:** `backend/globals.py` — shared `cache` (Redis) and `db` (SQLAlchemy) instances imported by both `__init__.py` and `utils.py`.

### Caching Strategy (Redis)

| Data | TTL |
|------|-----|
| Users list | 15 min |
| User duty | 10 min |
| Duty schedule | 2 hours |
| Sections | 1 hour |
| Feedback dates | 2 hours |

Each cached function has a corresponding `clear_*_cache()` function.

### Frontend

- **Entry:** `frontend/src/main.tsx` → `App.tsx` defines React Router routes.
- **API client:** `frontend/src/api.ts` — `apiCall()` wraps fetch and automatically injects the logged-in username into `X-Current-User` header, query params, and POST body. Use `apiGet()` / `apiPost()` wrappers throughout.
- **Auth:** Username stored in `localStorage` as `currentUser`. Validated via `GET /api/auth/validate` on load.
- **Vite proxy:** Dev server proxies `/api/`, `/get-`, `/select-`, `/devos-`, `/duty-` to the Flask backend.

### Data Flow

1. User logs in → username stored in `localStorage`
2. All API calls include username (header + query param + body)
3. Backend routes call utils functions → Redis cache or PostgreSQL
4. Flask serves the built React `index.html` for all non-API routes (`GET /`)

## CI/CD

GitHub Actions (`.github/workflows/python-app.yml`) runs on push/PR to `develop`:
1. Lint with flake8
2. Run pytest with coverage
3. Upload to Codecov (85% coverage target enforced)

Active development happens on `develop`; `main` is production.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`github.com/GlomeCS/BCSSM`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

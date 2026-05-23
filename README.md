# BCSSM

A full-stack web application for managing duty schedules, section rosters, and devotional feedback. Built with Flask (Python) and React (TypeScript), backed by PostgreSQL and Redis.

## Features

- **Duty scheduling** — view today's assigned duties and a 14-day rolling schedule with bi-weekly cycle support
- **Section management** — browse users grouped by section with search/filter
- **Devotional feedback** — leaders can submit and edit daily feedback entries by section
- **Role-based access** — leader vs. member views gated by authentication
- **Redis caching** — all heavy queries are cached to reduce database load

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, Flask 3, SQLAlchemy, Gunicorn |
| Frontend | React 19, TypeScript, Vite, Bootstrap 5 |
| Database | PostgreSQL (Supabase) |
| Cache | Redis 7 |
| Container | Docker + Docker Compose |

## Prerequisites

- Python 3.10+
- Node.js 20+
- A running PostgreSQL instance (Supabase or local)
- Redis 7 (or use Docker Compose, which starts one automatically)

## Environment Variables

Create a `.env` file in the repo root:

```env
# Flask
SECRET_KEY=your-secret-key

# PostgreSQL connection (Supabase or local)
host=your-db-host
port=5432
database=your-db-name
user=your-db-user
password=your-db-password

# Redis
REDIS_URL=redis://localhost:6379
```

## Running Locally

### Option 1 — Docker Compose (recommended)

Builds the full app (frontend + backend) and starts Redis automatically.

```bash
docker-compose up
```

The app is available at `http://localhost:8080`.

### Option 2 — Separate dev servers

Run the backend and frontend independently for hot-reload during development.

**Backend** (port 8080):

```bash
pip install -r backend/requirements.txt
python backend/bcssm_backend/__init__.py
```

**Frontend** (port 5173, proxies API calls to the backend):

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies all `/api/`, `/get-*`, `/select-*`, `/devos-*`, and `/duty-*` requests to the Flask backend on port 8080.

## Testing

**Backend:**

```bash
pytest backend/tests/
# With coverage
pytest backend/tests/ --cov=backend
```

**Frontend unit tests (Vitest):**

```bash
cd frontend
npm run test:run
```

**Frontend E2E tests (Playwright):**

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

## Project Structure

```
BCSSM/
├── backend/
│   ├── bcssm_backend/
│   │   ├── __init__.py       # App factory (create_app)
│   │   ├── routes/           # Thin route handlers
│   │   ├── utils.py          # All DB queries and cache logic
│   │   ├── auth.py           # Username/user-ID resolution
│   │   ├── cache_utils.py    # @cached_result decorator
│   │   └── exceptions.py     # Domain exception hierarchy
│   ├── globals.py            # Shared db and cache instances
│   ├── config.py             # Dev / Test / Prod configs
│   └── tests/                # pytest test suite
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # React Router routes
│   │   ├── api.ts            # apiGet / apiPost wrappers
│   │   └── *.tsx             # Page components
│   └── src/__tests__/        # Vitest + Playwright tests
├── docker-compose.yml
├── Dockerfile
└── .env                      # Local secrets (not committed)
```

## CI/CD

GitHub Actions runs on push/PR to `develop`:

- `frontend-unit-tests` — ESLint, TypeScript type-check, Vitest
- `frontend-e2e-tests` — Playwright (Chromium)
- `build` — flake8, pytest with coverage, upload to Codecov (85% target)

Production deployment uses Docker on Render; `main` is the production branch.

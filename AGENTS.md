# AGENTS.md

## Cursor Cloud specific instructions

Bugis is a DCI / EVPN line‑provisioning platform with two dev services:

- **Backend** — FastAPI (Python 3.13) in `backend/`, serves API on port **8000** (`/health`, `/docs`, `/api/v1/...`).
- **Frontend** — React + Vite (Node 24) in `frontend/`, dev server on port **5173**; Vite proxies `/api` and `/health` to `http://localhost:8000` (see `frontend/vite.config.ts`).

Standard commands live in the `Makefile` (`backend-run`, `backend-seed`, `backend-test`, `frontend-dev`, `frontend-build`). Notes below are the non‑obvious bits.

### Toolchain (already provisioned by the update script / snapshot)
- Node **24.16.0** is installed via nvm and symlinked into `~/.local/bin` so it shadows the runtime's default `/exec-daemon/node` (v22). Use `node`/`npm` normally; if a stale Node 22 ever appears, re-link with `ln -sf "$HOME/.nvm/versions/node/v24.16.0/bin/{node,npm,npx,corepack}" "$HOME/.local/bin/"`.
- Python **3.13** comes from `uv`. Backend deps live in a virtualenv at `backend/.venv` (no system `pip` for 3.13). Run backend tools via `backend/.venv/bin/...` (e.g. `.venv/bin/uvicorn`, `.venv/bin/python -m pytest`).

### Running the backend (IMPORTANT — SQLite gotcha)
- The Alembic migrations are **PostgreSQL-only** (they use `ALTER COLUMN ... SET DEFAULT`, invalid on SQLite). With the default local SQLite DB, running migrations on startup **fails / hangs the app's startup** (uvicorn never finishes "Waiting for application startup", so port 8000 returns connection-refused).
- Fix: set **`BUGIS_SKIP_MIGRATE=1`** as a real environment variable. The SQLite schema is built by SQLAlchemy `create_all()`, so skipping migrations is correct (this mirrors `backend/tests/conftest.py`). NOTE: this flag is read from `os.environ` directly, **not** from `backend/.env`, so it must be exported in the shell that launches uvicorn — putting it only in `.env` does nothing.
- Start: `cd backend && BUGIS_SKIP_MIGRATE=1 .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Seed demo data (sites/tenants/devices/circuits): `cd backend && BUGIS_SKIP_MIGRATE=1 .venv/bin/python -m scripts.seed`
- `backend/.env` is created for local dev with `BUGIS_DRY_RUN=true` (renders device config instead of pushing to real hardware) and `BUGIS_EXPOSE_OPENAPI=true`. Tests pass without it; the API server reads it.
- A PostgreSQL deployment (docker compose) does run the Alembic migrations normally; the skip flag is only for the SQLite dev path.

### Auth / login
- Default admin is `admin` / `admin123`.
- The programmatic/UI login endpoint is `POST /api/v1/auth/login/json` (JSON body `{"username","password"}`). The OAuth2 form endpoint `POST /api/v1/auth/login` currently returns 500, so use `/login/json`.

### Tests / build
- Backend tests: `cd backend && .venv/bin/python -m pytest -q` (conftest sets its own `BUGIS_SKIP_MIGRATE=1` + temp SQLite, so no extra env needed).
- Frontend build: `cd frontend && npm run build` (runs `tsc -b` then `vite build`).

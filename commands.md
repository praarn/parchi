# Commands

Everything you need to run, develop, test and ship Parchi. Paths are relative to
the repo root unless noted.

- **Repo layout**: `frontend/` (Next.js), `backend/` (FastAPI + worker),
  `database/schema.sql`, `samples/`, `docker-compose.yml`.
- **Ports**: web `3000`, API `8000`, Postgres `5432`.

---

## 1. Run the whole stack with Docker (recommended)

```bash
# One-time: create the backend env file and add a Groq API key
cp backend/.env.example backend/.env
#   then edit backend/.env  ->  GROQ_API_KEY=gsk_...      (free: https://console.groq.com/keys)
#   and set a JWT_SECRET:    python -c "import secrets; print(secrets.token_hex(32))"

docker compose up --build            # start postgres + api + worker + web
#   web   -> http://localhost:3000
#   API   -> http://localhost:8000/docs
#   worker logs stream in the same terminal

docker compose up -d --build         # ...detached
docker compose logs -f api worker    # follow specific services
docker compose ps                    # status + health
docker compose down                  # stop, keep data
docker compose down -v               # stop and WIPE the database volume
docker compose build                 # build images only
docker compose build --no-cache api  # force a clean rebuild of one image
```

The schema in `database/schema.sql` is applied automatically the first time the
`pg_data` volume is created. After changing the schema, recreate the volume:

```bash
docker compose down -v && docker compose up --build
```

---

## 2. Local development (no Docker for the app)

Postgres still runs in Docker; the API, worker and web run on the host.

```bash
docker compose up -d postgres        # just the database
```

### Backend — API + worker

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate                # Windows (PowerShell: .venv\Scripts\Activate.ps1)
# source .venv/bin/activate           # macOS / Linux
pip install -r requirements-dev.txt

cp .env.example .env                  # then set GROQ_API_KEY and JWT_SECRET
#   DATABASE_URL in .env already points at localhost:5432

# terminal 1 — API (auto-reload)
uvicorn app.main:app --reload --port 8000

# terminal 2 — background worker
python -m app.worker
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local            # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                           # http://localhost:3000
```

---

## 3. Database

```bash
# psql shell
docker compose exec postgres psql -U bureaucracy -d bureaucracy

# re-apply schema to an existing volume (safe: everything is IF NOT EXISTS)
docker compose exec -T postgres psql -U bureaucracy -d bureaucracy < database/schema.sql

# wipe just the documents/queue data (keeps users)
docker compose exec postgres psql -U bureaucracy -d bureaucracy \
  -c "TRUNCATE documents, jobs RESTART IDENTITY CASCADE;"
```

---

## 4. Tests, lint, types

### Backend

```bash
cd backend
pytest                       # DB-backed tests skip automatically if Postgres is down
pytest --cov=app             # with coverage
ruff check .                 # lint
ruff format .                # apply formatting
ruff format --check .        # verify formatting (what CI runs)
```

### Frontend

```bash
cd frontend
npm run lint                 # eslint (flat config)
npm run typecheck            # tsc --noEmit
npm run build                # production build
```

---

## 5. Sample documents

```bash
# regenerate samples/sample-notice.pdf and samples/sample-notice.png
backend/.venv/Scripts/python samples/make_samples.py     # any Python with pymupdf works
```

Upload `samples/sample-notice.pdf` (has a ruled table) or `sample-notice.png`
(exercises the multimodal image path) from the dashboard.

---

## 6. CI

`.github/workflows/ci.yml` runs on every push / PR to `main`:

| job | does |
|-----|------|
| `backend` | `ruff check` + `ruff format --check` + `pytest` against a pgvector service |
| `frontend` | `npm ci` + `npm run lint` + `npm run typecheck` + `npm run build` |
| `docker` | `docker compose build` (all images) |

---

## 7. Environment variables

`backend/.env` (see `backend/.env.example`):

| var | purpose |
|-----|---------|
| `DATABASE_URL` | Postgres connection string |
| `JWT_SECRET` | signs access-token JWTs — use a 64-char random hex |
| `ACCESS_TOKEN_TTL_MINUTES` / `REFRESH_TOKEN_TTL_DAYS` | token lifetimes (default 15 / 7) |
| `GROQ_API_KEY` | free key from console.groq.com — text + vision models |
| `GROQ_TEXT_MODEL` / `GROQ_VISION_MODEL` | model ids |
| `UPLOAD_DIR` | where uploaded files land |
| `MAX_UPLOAD_MB` | upload size cap (default 50) |
| `CORS_ORIGINS` | comma-separated allowed browser origins |
| `WORKER_POLL_INTERVAL_SECONDS` / `WORKER_STUCK_THRESHOLD_MINUTES` / `JOB_MAX_ATTEMPTS` | worker tuning |

`frontend/.env.local` (see `frontend/.env.example`):

| var | purpose |
|-----|---------|
| `NEXT_PUBLIC_API_URL` | base URL of the API (baked into the client bundle) |
| `NEXT_PUBLIC_WS_URL` | WebSocket origin for live progress |

# .github/workflows/ — CI

`ci.yml` runs on every push and PR to `main`. Three independent jobs:

| job | steps | why |
|-----|-------|-----|
| `backend` | spin up a `pgvector/pgvector:pg16` service, `pip install -r requirements-dev.txt`, apply `database/schema.sql`, `ruff check`, `ruff format --check`, `pytest` | the DB-backed tests need a real Postgres with pgvector; formatting is checked, not applied |
| `frontend` | `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build` | catches type errors and lint regressions, and proves the production build still compiles |
| `docker` | `cp backend/.env.example backend/.env` then `docker compose build` | proves all three images still build |

No Kubernetes, no external registry, no deploy step — this is a portfolio project;
CI's job is "does it still build and pass". `GROQ_API_KEY` in the backend job is a
dummy value: tests never call the LLM.

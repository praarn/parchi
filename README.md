# Parchi

**Government paperwork, in plain language.**

Upload a government notice, scheme, form or letter — as a PDF or just a **photo
of the page** — and get back:

- a plain-language **summary** and an *"explain it like I'm 10"* version
- an **eligibility checklist**: who can apply, documents needed, conditions, exclusions
- every **key date**, pulled out and dated
- any **tables** in the document, rebuilt as real tables
- a **chat** that answers your questions using *only* what's in the document
- all of it in **English, हिंदी, ಕನ್ನಡ, தமிழ், తెలుగు, मराठी or বাংলা**

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic — REST + WebSockets |
| Data / AI | pandas, NumPy, scikit-learn (LSA retrieval), Groq LLM (text + vision), RAG |
| Database | PostgreSQL + pgvector |
| Auth | JWT access + rotating refresh tokens |
| Infra | Docker + Docker Compose, GitHub Actions |
| Tests | Pytest + FastAPI TestClient |

```
frontend (Next.js)  ──REST + WebSocket──▶  backend (FastAPI)  ──▶  PostgreSQL + pgvector
                                                  ▲                        │
                                          NOTIFY progress          FOR UPDATE SKIP LOCKED
                                                  │                        ▼
                                            worker (python -m app.worker) runs the pipeline:
                                            extract → simplify → embed → tables
```

There is **no Node backend and no Redis** — the job queue is a Postgres table,
the worker is a Python process, and multimodal extraction (photos of documents)
goes through Groq's vision model with Tesseract OCR as an offline fallback.

## Repo layout

| path | what |
|------|------|
| `frontend/` | Next.js app — see `frontend/explanation.md` |
| `backend/` | FastAPI API + worker + document pipeline — see `backend/explanation.md` |
| `database/schema.sql` | the whole schema — see `database/explanation.md` |
| `samples/` | a sample notice (PDF + image) for testing |
| `docker-compose.yml` | postgres + api + worker + web |
| `commands.md` | **every command** to run, develop, test and ship |

## Quick start

```bash
cp backend/.env.example backend/.env
# edit backend/.env:  GROQ_API_KEY=gsk_...   (free, no card: https://console.groq.com/keys)
#                     JWT_SECRET=<64 hex chars>   python -c "import secrets; print(secrets.token_hex(32))"

docker compose up --build
```

- Web → http://localhost:3000
- API docs → http://localhost:8000/docs

Then sign up, upload `samples/sample-notice.pdf`, and watch the pipeline run live.

Full command reference — local dev per service, tests, lint, database, CI — is in
[`commands.md`](./commands.md). Architecture reasoning is in
[`PROJECT_DEEP_DIVE.md`](./PROJECT_DEEP_DIVE.md).

## Notes before deploying anywhere

- Rotate `JWT_SECRET` and `GROQ_API_KEY`; never ship dev values.
- Redact PII (Aadhaar / PAN) before sending document text to any LLM.
- Put the API behind TLS and lock `CORS_ORIGINS` to your real origin.

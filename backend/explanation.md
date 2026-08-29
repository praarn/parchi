# backend/ — why it's built this way

The whole backend is **one FastAPI codebase**. It replaces what used to be a
separate Node/Express API plus a Redis/BullMQ worker. Two processes run from the
same image:

| process | command | role |
|---------|---------|------|
| API | `uvicorn app.main:app` | all HTTP + WebSocket: auth, documents, chat, progress, stats |
| worker | `python -m app.worker` | drains the job queue and runs the document pipeline |

## Module map

```
app/
  config.py     typed settings (pydantic-settings) — one place, fails loud on a bad env
  db.py         psycopg connection pool + small query helpers + progress NOTIFY
  security.py   bcrypt hashing; access-JWT mint/verify; opaque refresh tokens
  deps.py       get_current_user (Bearer) dependency
  models.py     Pydantic request/response schemas
  events.py     LISTEN 'parchi_progress' -> fan out to WebSocket subscribers
  queue.py      the Postgres job queue (enqueue / claim / complete / fail / sweep)
  worker.py     the poll loop; owns the pipeline order and failure handling
  routers/      auth.py, documents.py, chat.py, ws.py
  pipeline/     see pipeline/explanation.md
```

## Decisions

**Queue in Postgres, not Redis.** A single `jobs` table claimed with
`SELECT … FOR UPDATE SKIP LOCKED` gives at-most-once delivery across any number
of workers, plus retries with exponential backoff, without adding a broker. The
target stack has no Redis, and the load here (a handful of documents at a time)
never justified one. `queue.py` is ~120 lines and does everything BullMQ did.

**Access + refresh tokens.** The access token is a short-lived (15 min) stateless
JWT — never stored. The refresh token is an opaque random string; only its
sha256 is kept in `refresh_tokens`, and `/auth/refresh` *rotates* it (old row
revoked, new one issued) so a stolen refresh token is single-use and its reuse
is detectable. `/auth/logout` just revokes.

**Live progress over WebSocket.** The worker writes each stage into
`documents.processing_stage` and fires `NOTIFY parchi_progress`. One listener
task per API process (`events.py`) fans notifications out to the WebSockets
watching that document. `routers/ws.py` also runs a slow safety poll and closes
itself on a terminal status, so a missed NOTIFY (or a platform where psycopg's
async listener can't run) still resolves within a few seconds.

**psycopg connection pool, sync.** FastAPI runs the sync endpoints in a
threadpool; the pipeline code is plain sync Python. Only the NOTIFY listener is
async. Every pooled connection is pinned to `client_encoding=UTF8` — libpq
otherwise picks up the host codepage on Windows and mangles ₹, curly quotes and
Devanagari.

## Tests

`tests/` uses FastAPI's `TestClient` + a real Postgres (`docker compose up -d
postgres`). DB-backed tests **skip** cleanly when Postgres is unreachable, so
`pytest` still runs the pure-logic tests (`chunk`, LSA embedding ranking)
anywhere. LLM calls are never made in tests.

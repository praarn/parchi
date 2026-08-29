# Parchi — deep dive

Why the project is built the way it is. For the *what* and the *how to run it*,
see `README.md` and `commands.md`.

---

## 1. The problem

A government notice is dense, full of cross-references, often bilingual, and
frequently arrives as a **photo** someone took of a printed page. The reader
wants four things fast: *what is this*, *does it apply to me*, *what do I have to
do*, *by when*. Parchi produces exactly those, plus a grounded chat for
follow-ups, in the reader's language.

---

## 2. Architecture

```
┌────────────┐   REST + WebSocket   ┌──────────────────────────┐
│  frontend  │ ───────────────────▶ │        backend (API)     │
│  Next.js   │ ◀─────────────────── │  FastAPI + Pydantic      │
└────────────┘                      └──────────┬───────────────┘
                                               │  SQL
                                     ┌─────────▼─────────┐
                                     │ PostgreSQL +       │
                                     │ pgvector          │
                                     └─────────▲─────────┘
                                               │ FOR UPDATE SKIP LOCKED
                                     ┌─────────┴─────────┐
                                     │  backend (worker) │  extract → simplify
                                     │  python -m        │  → embed → tables
                                     │  app.worker       │
                                     └───────────────────┘
```

**One backend codebase, two processes.** The API and the worker are the same
Python package (`backend/app`), started with different commands. They share the
database and nothing else.

### What changed from the original design

The project began as **Next.js → Express (Node) → Redis/BullMQ → Node worker →
FastAPI pipeline → Postgres**. That's four moving services and two languages for
what is, in the end, "accept a file, run a pipeline, store the result".

It's now **Next.js → FastAPI (+ worker) → Postgres**. The Express layer's jobs
(auth, uploads, dedup, chat, enqueueing) moved into FastAPI routers; the
BullMQ/Redis queue became a Postgres table; the Node worker became a Python poll
loop that reuses the exact same pipeline functions.

---

## 3. Key decisions

### 3.1 Job queue in Postgres, not Redis

```sql
SELECT id FROM jobs
 WHERE status = 'queued' AND run_after <= now()
 ORDER BY created_at
 FOR UPDATE SKIP LOCKED
 LIMIT 1;
```

`SKIP LOCKED` means N workers can run concurrently and never pick up the same
job. Retries are `run_after = now() + 5s * 2**attempts` until `max_attempts`,
then the document is marked `failed`. A periodic sweep fails any document stuck
at `processing` past a threshold (worker was down when the job was enqueued).

This is ~120 lines in `backend/app/queue.py` and removes an entire service. Redis
would earn its place at a scale this project doesn't have.

### 3.2 Auth — access + rotating refresh tokens

- **Access token**: stateless JWT, 15 min, `HS256`. Carries `sub` + `email`.
  Never stored server-side; verified on every request by a FastAPI dependency.
- **Refresh token**: opaque `secrets.token_urlsafe(48)`, 7 days. Only its
  **sha256** is stored (`refresh_tokens`). `/auth/refresh` **rotates**: the
  presented row is revoked and a fresh pair issued, so a stolen refresh token is
  single-use and its reuse shows up as a revoked-token hit. `/auth/logout`
  revokes.

The frontend keeps both in `localStorage` and the API client refreshes + retries
once transparently on a `401`.

### 3.3 Retrieval — deterministic LSA, no embeddings API

`backend/app/pipeline/embed.py` fits a small scikit-learn pipeline **per
document** on that document's own chunks:

```
FeatureUnion(word 1–2 grams, char 3–5 grams)  →  TruncatedSVD(≤256)  →  L2 normalise
```

- **No embeddings account, no per-query cost** — the app runs on a Groq key alone.
- **Deterministic** — reproducible retrieval, trivially unit-testable
  (`test_pipeline.py` asserts the right chunk ranks first for four plain-English
  questions).
- The fitted `(vectorizer, svd)` is pickled into `document_vectorizers` so a
  later question is projected into the **same** space the chunks live in.
- Char n-grams bridge morphology ("residency" ~ "residents") and
  transliteration wobble, which matters for multilingual government prose.

Vectors are stored in `VECTOR(256)` and searched with pgvector's cosine
operator + an ivfflat index. Upgrading to a hosted embedding model is one
function and one schema number.

### 3.4 Multimodal extraction

`pipeline/extract.py` is the front door:

- **PDF** → PyMuPDF native text; a page with almost no text is treated as
  scanned and sent through Tesseract when available.
- **Image** (png/jpg/webp — a photographed document) → Groq's Llama-4 Scout
  vision model transcribes it faithfully (and flags stamps/signatures on a
  `[VISUAL]` line), with Tesseract OCR as the offline fallback.

Everything downstream just sees `[{page_number, text}]`, so `simplify`, `embed`,
`chunk` and the RAG chat are identical regardless of input type.

### 3.5 Structured tables → pandas

`pipeline/tables.py` uses PyMuPDF `find_tables(strategy="lines_strict")` — ruled
tables only, near-zero false positives on prose — and normalises each through a
`pandas.DataFrame` into `{columns, rows}` JSON. The frontend renders them as real
tables instead of the run-on text OCR would produce. Borderless "tables" are
deliberately not chased; the alternative `text` strategy shreds paragraphs.

### 3.6 Live progress — WebSocket with a poll fallback

The worker writes each stage into `documents.processing_stage` and fires
`NOTIFY parchi_progress`. One listener task per API process (`events.py`) fans
each notification out to the WebSockets watching that document. `routers/ws.py`
also runs a slow safety poll and self-closes on a terminal status — so a missed
NOTIFY (or a platform where psycopg's async listener can't run) still resolves in
a few seconds. The frontend hook (`useDocumentProgress`) mirrors this: WS first,
polling if the socket won't hold.

### 3.7 pandas for the dashboard stats

`GET /documents/stats` aggregates counts by status, average page count, and a
14-day upload histogram with pandas `value_counts` / `groupby`. Small, but it's
the honest place for pandas in the request path alongside table extraction.

---

## 4. Request lifecycle

1. **Sign up / sign in** → access + refresh tokens.
2. **Upload** (`POST /documents/upload`) → bytes hashed (sha256), deduped
   **per user**, stored with the real file extension, row inserted as `uploaded`.
3. **Process** (`POST /documents/{id}/process`) → status → `processing`, a row
   added to `jobs`.
4. **Worker** claims the job, then per stage: `extracting` → `simplifying` →
   `embedding` → `tables` → `finalizing`, writing `processing_stage` + NOTIFY
   after each. Insight + tables land in their tables; status → `ready`.
5. **Frontend** shows the staged checklist over WebSocket, then loads the
   English insight + tables.
6. **Translate** (`POST /documents/{id}/translate`) → cached per
   `(document, language)`.
7. **Chat** (`POST /documents/{id}/chat`) → top-k chunk retrieval → answer
   grounded only in that context, with the page numbers it used.

---

## 5. Deliberate trade-offs

| Today | Upgrade path |
|-------|--------------|
| Retrieval: per-document LSA (sklearn) | Swap `embed.py` for a hosted embedding model; bump `VECTOR(256)` |
| LLM: Groq free tier | Change `llm_client.py` — model ids are in `config.py` |
| File storage: shared Docker volume | S3 + presigned upload URLs in `routers/documents.py` |
| Progress fan-out: in-process registry | Fine for one API replica; for many, fan out through Postgres NOTIFY only (already the transport) |
| Auth: email + password | Add OAuth / phone OTP alongside the existing token scheme |
| No PII redaction | Redact Aadhaar/PAN before any text reaches the LLM |

---

## 6. Testing

- `backend/tests/` — FastAPI `TestClient` against a real pgvector Postgres.
  Covers the full auth lifecycle (signup → login → me → refresh rotation →
  logout revocation), upload / dedup / per-user isolation / queueing, stats
  shape, and pure-logic pipeline tests (chunk boundaries incl. Devanagari, LSA
  ranking). DB-backed tests skip cleanly with no database.
- `.github/workflows/ci.yml` — `backend` (ruff + pytest on a pgvector service),
  `frontend` (lint + typecheck + build), `docker` (compose build).

# Parchi — implementation

How the system is built, end to end: the process model, the data model, every
stage of the document pipeline, the auth scheme, the live-progress transport, and
the deliberate trade-offs. For *what it does* see `README.md`; for *how to run
it* see `commands.md`. Per-directory notes live in `backend/explanation.md`,
`frontend/explanation.md`, `database/explanation.md`,
`backend/app/pipeline/explanation.md`.

---

## 1. The problem, precisely

A government notice is dense, cross-referenced, often bilingual, and frequently
arrives as a **photo of a printed page**. A reader wants four things fast:

1. *What is this?* — a plain-language summary.
2. *Does it apply to me?* — who can apply, what documents, what conditions, what
   disqualifies.
3. *What must I do, and by when?* — actions and dated deadlines.
4. *Follow-ups* — a chat that answers **only** from the document, citing pages.

…all in the reader's language (English, Hindi, Kannada, Tamil, Telugu, Marathi,
Bengali).

Everything below exists to turn an arbitrary PDF or photo into those four
artefacts, reproducibly, on a single free LLM key.

---

## 2. Architecture

```
┌────────────┐   REST + WebSocket   ┌──────────────────────────┐
│  frontend  │ ───────────────────▶ │      backend — API       │
│  Next.js16 │ ◀─────────────────── │  uvicorn app.main:app    │
└────────────┘                      └──────────┬───────────────┘
                                               │ SQL (psycopg pool)
                                     ┌─────────▼──────────┐
                                     │ PostgreSQL 16 +    │
                                     │ pgvector          │
                                     │  • jobs (queue)    │
                                     │  • NOTIFY channel  │
                                     └─────────▲──────────┘
                    LISTEN parchi_progress     │ FOR UPDATE SKIP LOCKED
                                     ┌─────────┴──────────┐
                                     │   backend — worker │
                                     │ python -m app.worker│
                                     │ extract→simplify→   │
                                     │ embed→tables→final  │
                                     └────────────────────┘
```

### 2.1 One codebase, two processes

The API and the worker are the **same Python package** (`backend/app`), started
with different commands and sharing nothing but the database:

| process | command | responsibility |
|---|---|---|
| API | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | all HTTP + WebSocket: auth, upload, document CRUD, translate, tables, share, stats, chat, live-progress socket |
| worker | `python -m app.worker` | drain the `jobs` table, run the document pipeline, write progress + terminal status |

Both are built from `backend/Dockerfile`; `docker-compose.yml` runs the worker by
overriding `command:` and disabling the image's HTTP healthcheck.

### 2.2 What changed from the original design, and why

The project began as **Next.js → Express (Node) → Redis/BullMQ → Node worker →
FastAPI pipeline → Postgres**: four services, two languages, for what is
ultimately "accept a file, run a pipeline, store the result".

It is now **Next.js → FastAPI (+ worker) → Postgres**:

| removed | replaced by | rationale |
|---|---|---|
| Express API layer | FastAPI routers (`routers/auth.py`, `documents.py`, `chat.py`, `ws.py`) | one language, one framework, Pydantic validation for free |
| Redis + BullMQ | a `jobs` table claimed with `FOR UPDATE SKIP LOCKED` (`app/queue.py`, ~120 lines) | no broker to run; the load here (a few documents at a time) never justified one |
| Node worker | `python -m app.worker` poll loop | calls the *exact same* pipeline functions the API imports; no RPC boundary |
| Pinecone / hosted embeddings | per-document TF-IDF → SVD in `pipeline/embed.py`, vectors in `pgvector` | zero embeddings account, zero per-query cost, fully deterministic |
| Separate OCR service | PyMuPDF native text + Groq vision + Tesseract fallback, all in `pipeline/extract.py` | multimodal in-process, degrades instead of hard-failing |

The target stack for this portfolio is FastAPI + Postgres + Next.js with Docker
Compose and GitHub Actions — no Kubernetes, no external brokers, no managed
vector DB. Every decision below is downstream of that.

---

## 3. Runtime & wiring

### 3.1 Config — `app/config.py`

One typed `pydantic-settings` model. A missing or misspelled env var fails
**at process start**, not as a confusing runtime error later. `get_settings()` is
`lru_cache`d; `settings` is the module-level singleton everything imports.

Notable fields (full list in `commands.md §7` and `.env.example`):

| field | default | notes |
|---|---|---|
| `database_url` | `postgresql://bureaucracy:bureaucracy@localhost:5432/bureaucracy` | compose overrides host to `postgres` |
| `jwt_secret` / `jwt_algorithm` | `dev-only-insecure-change-me` / `HS256` | must be rotated for any real deploy |
| `access_token_ttl_minutes` / `refresh_token_ttl_days` | `15` / `7` | |
| `upload_dir` / `max_upload_mb` | `./uploads` / `50` | compose mounts a shared volume at `/data/uploads` |
| `groq_api_key` | `""` | the only external credential the app needs |
| `groq_text_model` | `openai/gpt-oss-120b` | summary, translation, chat |
| `groq_vision_model` | `meta-llama/llama-4-scout-17b-16e-instruct` | image transcription |
| `worker_poll_interval_seconds` | `2.0` | sleep between empty `claim_next()` polls |
| `worker_stuck_threshold_minutes` | `15` | age past which a `processing` document is swept to `failed` |
| `job_max_attempts` | `3` | retries before a job is permanently `failed` |
| `enable_progress_listener` | `true` | set `false` in tests (TestClient cycles the lifespan per test) |
| `cors_origins` | `http://localhost:3000` | comma-separated; parsed by `cors_origin_list` |

`.env` is read as `utf-8-sig` so a BOM from a Windows editor doesn't corrupt the
first var.

### 3.2 Database access — `app/db.py`

- **One process-wide `psycopg_pool.ConnectionPool`** (`min_size=1`, `max_size=10`),
  opened lazily on first use, closed from the API lifespan and the worker's
  shutdown path.
- Every pooled connection is configured in `_configure()`:
  - `autocommit = True` (each helper is a single statement or an explicit block),
  - `SET client_encoding TO 'UTF8'` — libpq otherwise inherits the host ANSI
    codepage on Windows and mangles `₹`, curly quotes and Devanagari on the way
    out,
  - `register_vector(conn)` so `VECTOR` columns round-trip as Python lists / numpy
    arrays.
- Row factory is `dict_row` everywhere.
- Helpers: `query_all`, `query_one`, `execute`, and a `cursor()` context manager.
- Pipeline-adjacent helpers also live here so raw text survives one run:
  `store_document_text()`, `update_processing_stage()` (UPDATE + `pg_notify`),
  `notify_status()` (terminal-status `pg_notify`).

### 3.3 API app — `app/main.py`

- On Windows, swaps in `WindowsSelectorEventLoopPolicy` before anything imports
  psycopg async — the Proactor loop can't run psycopg's async listener. No-op on
  Linux/Docker.
- `lifespan`: opens the pool eagerly (so a bad `DATABASE_URL` fails at boot),
  starts the `pg_listener` task when `enable_progress_listener`, and on shutdown
  cancels the listener (5 s grace) and closes the pool.
- CORS middleware from `settings.cors_origin_list`, `allow_credentials=True`.
- Routers: `auth`, `documents`, `chat`, `ws`. Plus `GET /health` → `{"status":"ok"}`
  (the Docker healthcheck).

---

## 4. Data model — `database/schema.sql`

`schema.sql` is the **entire** schema. Docker mounts it into the Postgres image's
`docker-entrypoint-initdb.d/`, so it runs once when the `pg_data` volume is first
created. Everything is `CREATE … IF NOT EXISTS`, so re-applying by hand is safe.
There is **no migration tool** — "recreate the volume" is the reset story
(`docker compose down -v && docker compose up --build`). Extensions: `pgcrypto`
(for `gen_random_uuid()`), `vector` (pgvector). Both ship in
`pgvector/pgvector:pg16`.

### 4.1 Tables

| table | key columns | notes |
|---|---|---|
| `users` | `id uuid pk`, `email unique`, `password_hash`, `preferred_language` | `password_hash` is bcrypt (cost 12) |
| `refresh_tokens` | `token_hash unique`, `user_id fk`, `expires_at`, `revoked_at` | stores only **sha256** of the opaque token; `revoked_at` drives rotation & logout |
| `documents` | `id`, `user_id fk`, `file_url`, `file_hash`, `mime_type`, `status`, `processing_stage`, `processing_started_at`, `page_count`, `UNIQUE(user_id, file_hash)` | `status ∈ uploaded\|processing\|ready\|failed`; dedup is **per user** |
| `document_text` | `document_id fk`, `page_number`, `content` | raw per-page extracted text, kept so re-chunking / debugging doesn't re-read the source file |
| `document_insights` | `document_id fk`, `language`, `summary`, `key_points jsonb`, `deadlines jsonb`, `eligibility jsonb`, `explain_like_10`, `UNIQUE(document_id, language)` | English row written by the pipeline; other languages by cached translations |
| `document_tables` | `document_id fk`, `page_number`, `data jsonb` | `data = {columns:[…], rows:[[…],…]}` from `pipeline/tables.py` |
| `embeddings` | `document_id fk`, `chunk_index`, `page_number`, `text`, `embedding VECTOR(256)` | one row per chunk; ivfflat cosine index |
| `document_vectorizers` | `document_id pk`, `payload bytea`, `n_components` | the pickled `(FeatureUnion → SVD → Normalizer)` pipeline for that document |
| `chat_sessions` | `document_id fk`, `user_id fk` | one session per `(document, user)`; the latest is reused |
| `chat_messages` | `session_id fk`, `role`, `content`, `language` | full turn history, ascending by `created_at` |
| `jobs` | `document_id fk`, `type`, `status`, `attempts`, `max_attempts`, `run_after`, `locked_at`, `locked_by`, `last_error` | the Postgres-backed queue; `status ∈ queued\|running\|done\|failed` |

### 4.2 Indexes

`idx_documents_user`, `idx_chat_messages_session`, `idx_embeddings_document`,
`idx_refresh_tokens_user`, `idx_document_tables_document`,
`idx_jobs_claim (status, run_after, created_at)` — matches the queue's claim
predicate exactly — and

```sql
idx_embeddings_vector  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
```

Approximate-nearest-neighbour for the cosine search in `retrieve_top_chunks()`.
`lists = 100` suits small-to-medium row counts; a large corpus would tune toward
`sqrt(row_count)`.

### 4.3 Why `VECTOR(256)`

The retrieval embeddings are a per-document TF-IDF → `TruncatedSVD` projection,
not a hosted model. 256 dims is ample for documents with well under a few hundred
chunks and keeps the ivfflat index small. Changing the embedding method means
changing this number **and** `DIM` in `embed.py` together.

---

## 5. Authentication — `app/security.py`, `app/deps.py`, `routers/auth.py`

Two-token scheme.

### 5.1 Access token — stateless JWT

- `HS256`, `access_token_ttl_minutes` (15) TTL.
- Payload: `sub` (user id), `email`, `type: "access"`, `iat`, `exp`.
- **Never stored server-side.** Verified on every protected request by the
  `get_current_user` dependency (`app/deps.py`): parses `Authorization: Bearer …`
  via `HTTPBearer(auto_error=False)`, calls `decode_access_token()` (which also
  rejects a token whose `type != "access"`), then loads the user row — a deleted
  user's live token still 401s.
- Distinct error details: missing token, expired (`jwt.ExpiredSignatureError`),
  invalid, user-gone — each `401` with `WWW-Authenticate: Bearer`.

### 5.2 Refresh token — opaque, hashed, rotating

- `secrets.token_urlsafe(48)`, `refresh_token_ttl_days` (7) TTL.
- Only its **sha256** is stored (`refresh_tokens.token_hash`). A DB leak cannot be
  replayed.
- `_issue_pair()` inserts a fresh hash row and returns `{access, refresh}`.
- `POST /auth/refresh` **rotates**: looks up the presented token's hash; rejects
  if absent, revoked, or expired; revokes that row (`revoked_at = now()`); issues
  a brand-new pair. A stolen refresh token is therefore single-use, and its reuse
  after the legitimate client has rotated shows up as a revoked-token `401` —
  detectable.
- `POST /auth/logout` just sets `revoked_at` on the presented hash.

### 5.3 Endpoints

| method + path | body | returns |
|---|---|---|
| `POST /auth/signup` | `email, password (8–128), name?, preferred_language?` | `201` + `AuthResponse` (`user` + token pair); `409` on duplicate email |
| `POST /auth/login` | `email, password` | `AuthResponse`; `401` on bad creds (same message for unknown email vs wrong password) |
| `POST /auth/refresh` | `refresh_token` | `TokenPair`; `401` if invalid/expired/revoked |
| `POST /auth/logout` | `refresh_token` | `{"status": "logged_out"}` (idempotent) |
| `GET /auth/me` | — (Bearer) | `UserOut` |

### 5.4 Client side — `frontend/lib/api-client.ts`

- Both tokens in `localStorage` (`parchi_access`, `parchi_refresh`) so a reload
  stays signed in.
- Every request attaches the bearer token. On a `401` with `allowRetry`, it calls
  `tryRefresh()` **once** (de-duplicated with a module-level `refreshInFlight`
  promise so concurrent 401s trigger a single refresh) and retries the original
  request once. A failed refresh clears both tokens.
- `subscribeAuth()` + a `storage` event listener → `useIsAuthed()`
  (`useSyncExternalStore`) updates the UI on sign-in/out, including from another
  tab.
- The WebSocket URL carries the access token in the query string
  (`documentWsUrl()`), because browsers can't set an `Authorization` header on a
  `WebSocket`.

---

## 6. The job queue — `app/queue.py`

A single `jobs` table. No Redis, no broker.

### 6.1 Enqueue

`enqueue(document_id, type="process-document")`:

```sql
DELETE FROM jobs WHERE document_id = %s AND status IN ('queued', 'failed');
INSERT INTO jobs (document_id, type, max_attempts) VALUES (%s, %s, %s) RETURNING *;
```

Deleting stale `queued`/`failed` rows first makes re-processing a document
idempotent — you never stack duplicate jobs.

### 6.2 Claim

`claim_next()` — the core of the design:

```sql
WITH next AS (
    SELECT id FROM jobs
     WHERE status = 'queued' AND run_after <= now()
     ORDER BY created_at
     FOR UPDATE SKIP LOCKED
     LIMIT 1
)
UPDATE jobs j
   SET status = 'running', attempts = j.attempts + 1,
       locked_at = now(), locked_by = %s, updated_at = now()
  FROM next WHERE j.id = next.id
RETURNING j.*;
```

`FOR UPDATE SKIP LOCKED` means N worker processes can poll concurrently and each
gets a **different** row — no double processing, no external lock manager.
`locked_by` is `"{hostname}:{pid}"` for debugging. The claim and the
`status → running` write are the same statement, so a crash between "selected"
and "marked running" is impossible.

### 6.3 Complete / fail / retry

- `complete(job_id)` → `status = 'done'`, `last_error = NULL`.
- `fail(job, error)`:
  - if `attempts >= max_attempts` → `status = 'failed'`, store `error[:2000]`,
    return `True` (permanent).
  - else re-queue: `status = 'queued'`,
    `run_after = now() + 5s · 2**attempts` (5s, 10s, 20s…), clear the lock,
    return `False`.
- The worker's `_handle_failure()` calls `fail()`; on a permanent failure it also
  flips the document to `status = 'failed'`, `processing_stage = 'failed'` and
  fires a terminal NOTIFY.

### 6.4 Stuck sweep

`sweep_stuck()` runs at most once a minute from the worker loop:

```sql
UPDATE documents
   SET status = 'failed', processing_stage = 'failed'
 WHERE status = 'processing'
   AND processing_started_at < now() - interval '<threshold> minutes'
RETURNING id;
```

This catches the case where a document was set to `processing` and enqueued while
no worker was running long enough for the job row to matter — without it the UI
would spin forever.

---

## 7. Request lifecycle

1. **Sign up / sign in** → access + refresh tokens (`§5`).

2. **Upload** — `POST /documents/upload` (multipart, Bearer):
   - MIME must be in `{application/pdf, image/png, image/jpeg, image/webp}` →
     else `415`. The real extension is derived from the MIME, not the filename.
   - Size ≤ `max_upload_bytes` → else `413`; empty → `400`.
   - `file_hash = sha256(bytes)`. If a row already exists for
     `(file_hash, user_id)` → return it with `deduped: true` (no rewrite). Dedup
     is **per user**: two people uploading the same public notice each get their
     own document; one person re-uploading a file they already have
     short-circuits.
   - Otherwise write bytes to `UPLOAD_DIR/{uuid4}{ext}`, insert `documents` row as
     `status = 'uploaded'`, return `201` + `deduped: false`.

3. **Process** — `POST /documents/{id}/process` (ownership-checked):
   `status → 'processing'`, `processing_stage → NULL`,
   `processing_started_at → now()`, then `enqueue(id)`. Returns
   `{"status": "processing"}`.

4. **Worker** — `process_document(job)` in `app/worker.py`, per stage writing
   `processing_stage` + `NOTIFY parchi_progress`:

   | stage | call | writes |
   |---|---|---|
   | `extracting` | `extract_text(file_url, mime_type)` → `store_document_text()` | `document_text` rows |
   | `simplifying` | `simplify_document(full_text)` | (held in memory) |
   | `embedding` | `embed_and_store(id, chunk_pages(pages))` | `document_vectorizers`, `embeddings` |
   | `tables` | `_store_tables(id, extract_tables(file_url, mime_type))` | `document_tables` |
   | `finalizing` | `_upsert_insight(id, insight)`; `documents.status='ready'`, `page_count=len(pages)` | `document_insights` (`language='en'`, upsert on `(document_id, language)`) |

   Then `notify_status(id, "ready", "finalizing")` and `complete(job["id"])`.
   Any exception → `_handle_failure()` → queue decides retry vs. permanent fail.
   A job pointing at a since-deleted document is completed and dropped.

   (`processing_stage` can also be `vision` — the frontend's `ProgressStages`
   only renders that row once it has actually seen it, so PDF runs don't show a
   step they skip.)

5. **Frontend** shows the staged checklist over WebSocket (`§9`), then on `ready`
   pulls the English insight and tables once.

6. **Translate** — `POST /documents/{id}/translate` `{language}`:
   - `en` → `400` (already English).
   - If a `document_insights` row exists for `(id, language)` → return it,
     `cached: true`.
   - Else require the English row (`409` if the document hasn't finished), call
     `translate_insight(english, language)`, insert the translated row, return
     `cached: false`.

7. **Chat** — `POST /documents/{id}/chat` `{message, language}`:
   - get-or-create the `(document, user)` chat session,
   - load prior turns, insert the user message,
   - `answer_question(id, message, history, language)` → retrieve top-k chunks,
     answer grounded only in them,
   - insert the assistant message, return `{answer, sources: [page numbers]}`.
   - `GET /documents/{id}/chat` returns the full transcript.

8. **Share** — `POST /documents/{id}/share?language=…` builds a
   `https://wa.me/?text=…` URL from the summary + a link back to
   `{origin}/document/{id}`.

9. **Stats** — `GET /documents/stats` (`§8`).

---

## 8. The document pipeline — `app/pipeline/`

Every module is a plain function with no framework dependency, so it is
unit-testable and shared verbatim between the API (translate, chat) and the
worker (extract → finalize).

### 8.1 Extract — `extract.py` (the multimodal front door)

Input: a file path + MIME. Output downstream **always**
`list[{page_number: int, text: str}]`, so `chunk` / `simplify` / `embed` /
`tables` never branch on input type.

- **PDF** (`_extract_pdf`): PyMuPDF `page.get_text("text")` page by page. If a
  page yields `< 40` chars **and** OCR tooling is present, rasterise just that
  page with `pdf2image.convert_from_path(first_page=i, last_page=i)` and run
  `pytesseract` with `lang="eng+hin"`. On any OCR error, keep the native text.
- **Image** (`_extract_image`, png/jpg/webp — a photographed page): try
  `vision.describe_document_image(path)` (Groq). If that raises, fall back to
  `pytesseract` (`eng+hin`). If the vision result is still `< 40` chars, run OCR
  too and keep whichever is longer. Returned as a single page.
- `clean_text()` collapses whitespace and strips `Page N of M` boilerplate.
- OCR is **optional at runtime**: `import pytesseract, pdf2image` is guarded;
  `OCR_AVAILABLE = False` degrades instead of crashing. The Docker image installs
  `tesseract-ocr`, `tesseract-ocr-hin`, `poppler-utils`.

### 8.2 Vision — `vision.py`

`describe_document_image()` → `llm_client.call_vision()` with the Groq vision
model. The prompt asks for a **faithful, complete transcription** preserving
reading order and line breaks, exact numbers/dates/form numbers, and a trailing
`[VISUAL]` line noting stamps, seals, signatures, checkboxes, handwriting or
tables — explicitly **not** a summary. Raises on API failure so the caller can
fall back to OCR.

### 8.3 Chunk — `chunk.py`

`chunk_pages(pages)` → overlapping ~500-token chunks
(`CHUNK_SIZE = 500`, `CHUNK_OVERLAP = 100`, `tiktoken` `cl100k_base`).

- Split into sentences on `(?<=[.!?।॥])\s+` — Latin terminators **plus** the
  Devanagari danda `।` and double danda `॥`. The original code split on `.`
  only, which turned every non-Latin page into one giant run-on "sentence" with
  no real chunk boundaries — a real gap for an app that targets multilingual
  government prose.
- Accumulate sentences into a buffer; when adding the next one would exceed
  `CHUNK_SIZE`, flush the buffer as a chunk and start the next buffer with the
  last `CHUNK_OVERLAP` tokens of the previous one (decoded back to text) so
  context straddles the boundary.
- `chunk_index` is a document-global running counter; `page_number` is carried
  through. `test_pipeline.py` asserts indices are sequential and that Devanagari
  survives.

### 8.4 Embed & retrieve — `embed.py` (deterministic LSA, no embeddings API)

Per document, `_build_transformer(texts)` fits a small scikit-learn pipeline on
**that document's own chunks**:

```
FeatureUnion(
    word : TfidfVectorizer(ngram_range=(1,2), sublinear_tf, max_df=0.95)
    char : TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), sublinear_tf)
)  →  TruncatedSVD(n_components ≤ 256, random_state=42)  →  Normalizer(L2)
```

- `n_components = min(256, n_features - 1, n_chunks - 1)`, floored at 1.
- **Very short documents** (`< 3` non-empty chunks) can't support SVD → fall back
  to a stateless `HashingVectorizer(n_features=256, char_wb 3–5 grams, l2)`.
- Every vector is padded/truncated to exactly 256 (`_pad`) for the
  `VECTOR(256)` column.
- Word 1–2 grams carry topical signal; **char 3–5 grams** bridge morphology
  ("residency" ~ "residents") and transliteration wobble — which matters for
  multilingual government text.

`embed_and_store(document_id, chunks)`:
1. fit the transformer, `pickle` it into `document_vectorizers` (upsert on
   `document_id`),
2. `DELETE FROM embeddings WHERE document_id = …`, then insert one row per chunk
   with its 256-d vector.

`retrieve_top_chunks(document_id, question, top_k=5)`:
- load and unpickle the document's transformer,
- project the question into the **same** space, then

  ```sql
  SELECT page_number, text FROM embeddings
   WHERE document_id = %s
   ORDER BY embedding <=> %s::vector   -- pgvector cosine distance
   LIMIT %s;
  ```

- if no transformer exists (a document embedded before this pipeline), degrade to
  an `ILIKE` keyword scan rather than returning nothing.

**Why not a hosted embedding model:** the whole app runs on a Groq key alone — no
embeddings account, no per-query cost — and retrieval is fully deterministic, so
`test_pipeline.py` can assert the right chunk ranks first for four plain-English
questions. The trade-off is lower semantic recall than a large model; the
word+char TF-IDF union claws back most of what bag-of-words loses. Upgrading is
one function plus one schema number.

### 8.5 Simplify — `simplify.py`

`simplify_document(full_text)` → `llm_client.call_json()` (Groq JSON mode) with
the first 60 000 chars of text. Returns exactly:

```json
{
  "summary": "2–3 sentences — must never be empty",
  "key_points": ["…"],
  "deadlines": [{"description": "…", "date": "YYYY-MM-DD or null"}],
  "explain_like_10": "one very simple paragraph",
  "eligibility": {
    "who_can_apply": ["…"], "required_documents": ["…"],
    "conditions": ["…"], "exclusions": ["…"]
  }
}
```

The prompt insists `summary` / `key_points` / `explain_like_10` are always filled
regardless of document type; only `eligibility` / `deadlines` may be empty when
the document genuinely has none. Empty text raises before any API call; an empty
summary from the model is logged as a warning.

### 8.6 QA — `qa.py`

`answer_question(document_id, question, history, language)`:
- `retrieve_top_chunks(..., top_k=5)`, join as
  `"[page N] <text>"` blocks into the context,
- replay the last 6 turns (3 exchanges) of history,
- `call_text()` with a system prompt that says: answer **only** from the provided
  context; if the answer isn't there, say so plainly; never guess or use outside
  knowledge; keep it short and in `{language}`,
- return `{answer, sources: [page numbers of the retrieved chunks]}`.

### 8.7 Translate — `translate.py`

`translate_insight(insight, language_code)` → `call_json()` with a prompt that
translates the whole insight object into the target language (`hi/kn/ta/te/mr/bn`
→ full name), preserving meaning and tone over word-for-word, keeping official
terms (scheme names, form numbers) in their original form with a short
in-language gloss, at roughly an 8th-grade reading level. Same JSON shape as the
input. The router caches the result as a `document_insights` row.

### 8.8 Tables — `tables.py` (PyMuPDF → pandas)

`extract_tables(file_path, mime_type)`:
- images / non-PDFs → `[]` (their `[VISUAL]` line already flags visible tables).
- For each page: `page.find_tables(strategy="lines_strict")` — **ruled** tables
  only, essentially zero false positives on prose.
- `_clean_grid()` stringifies cells, drops fully-empty spacer rows. Need ≥ 2 rows
  and ≥ 2 columns. First row → header (blank cells become `col_{i}`), rest →
  body. Normalise through a `pandas.DataFrame` → `{columns, rows}` JSON.
- Cap at `MAX_TABLES = 25`.
- Borderless / whitespace-aligned "tables" are deliberately **not** chased — the
  `text` strategy shreds any dense paragraph into a mangled grid, which is worse
  than showing nothing.

### 8.9 LLM client — `llm_client.py`

Thin wrapper over the Groq SDK, lazily constructed (clear error if
`GROQ_API_KEY` is unset). Three entry points:

- `call_json(system, user, max_tokens=1500)` — `response_format={"type":"json_object"}`;
  `_extract_json()` strips stray ``` / ```json fences; on a `JSONDecodeError`
  it retries **once** with `"Return ONLY the JSON object. No prose, no markdown
  fences."` appended, then raises.
- `call_text(system, messages, max_tokens=800)` — free-form (chat).
- `call_vision(system, prompt, image_path, max_tokens=1500)` — base64-inlines the
  image as a `data:` URL alongside the text prompt.

### 8.10 Stats — `routers/documents.py::stats`

`GET /documents/stats` loads `(status, page_count, created_at)` for the user into
a `pandas.DataFrame` and computes:
- `by_status` via `value_counts()`,
- `avg_page_count` via `dropna().mean()` rounded to 1 dp,
- `uploads_last_14_days`: `groupby(day).size()` reindexed onto a fixed 14-day
  window (always 14 entries, zero-filled) — the dashboard renders it as a bar
  sparkline.

This plus table extraction is the honest place pandas earns its keep in this
codebase.

---

## 9. Live progress — WebSocket with a poll fallback

The worker runs in a **separate container**, so it can't call into the API
process. The transport is Postgres `NOTIFY`.

### 9.1 Worker side

`db.update_processing_stage(id, stage)` = `UPDATE documents SET processing_stage`
+ `SELECT pg_notify('parchi_progress', '{"document_id":…, "stage":…}')`.
`db.notify_status(id, status, stage)` fires a terminal payload with `status` set.

### 9.2 API side — `app/events.py`

- One `pg_listener(stop)` task per API process holds a **dedicated async
  connection**, `LISTEN parchi_progress`, and for each notification fans the
  parsed payload out to the `WebSocket`s registered for that `document_id`
  (`_subscribers: dict[str, set[WebSocket]]`, guarded by an `asyncio.Lock`).
- Self-healing: on a connection error it logs once and reconnects every 15 s; a
  send failure to a socket unregisters it.
- If the async listener can't run at all (platform / loop constraints), it warns
  once and the WebSocket endpoint's own poll still delivers progress.

### 9.3 Socket endpoint — `routers/ws.py`

`GET /ws/documents/{id}?token=<access token>`:
1. decode the access token from the query string (browsers can't set a WS
   `Authorization` header) → `4401` on failure,
2. confirm the caller owns the document → `4404` otherwise,
3. `accept()`, `register()`, immediately send the current `{status, stage}` (late
   joiners catch up), return early if already terminal,
4. loop: `await receive_text()` with a 3 s timeout; on timeout, re-read the row
   and push `{status, stage}`; break on a terminal `ready`/`failed` or a
   disconnect. This is the **safety poll** — a missed NOTIFY still resolves in a
   few seconds.
5. `unregister()` in `finally`.

### 9.4 Frontend — `lib/useDocumentProgress.ts`

Opens the WebSocket; on `onerror` / unexpected `onclose` (and while not yet
terminal) it starts polling `GET /documents/{id}` every 2.5 s. Either path
settles on `ready` / `failed`. `components/ProgressStages.tsx` renders the stage
as a six-step checklist (with the `vision` step shown only once seen).

---

## 10. Frontend — `frontend/`

Next.js 16 (App Router) + TypeScript + Tailwind. No component library — the
design system is a handful of `@layer components` classes in `app/globals.css`
(`.card`, `.btn-primary`, `.input`, …) plus tokens in `tailwind.config.ts`
(warm "civic paper": bone paper, deep teal, amber accent, Fraunces + Inter,
`focus-visible` rings, `prefers-reduced-motion` honoured).

### 10.1 Routes

| route | purpose |
|---|---|
| `/` | landing — what Parchi does, one CTA |
| `/login` | sign in / sign up (`components/AuthForm.tsx`) |
| `/dashboard` | upload zone, usage stats (pandas-backed sparkline), document list |
| `/document/[id]` | live progress → summary + eligibility/dates + tables + grounded chat |

### 10.2 Data flow

- **`lib/api-client.ts`** — the *only* module that talks to the API: token
  storage, bearer attach, transparent single refresh+retry on `401`, FastAPI
  `{detail}` error parsing (string or validation array), typed `api.*` methods.
- **`app/dashboard/page.tsx`** — redirects to `/login` if unauthenticated;
  `Promise.all([listDocuments, getStats])`; on file select →
  `uploadDocument` → `processDocument` → navigate to `/document/{id}`.
- **`app/document/[id]/page.tsx`** — `useDocumentProgress(id, {status:"processing"})`;
  on `ready` pulls the English insight + tables once; language change either
  re-fetches `en` or calls `translateDocument` and swaps the insight; share opens
  the `wa.me` URL. `parseMaybeJson` tolerates JSONB coming back as a string.
- **`components/ChatWindow.tsx`** — loads history, optimistic user bubble,
  `sendChatMessage`, renders `Source: page …` from `sources`.

### 10.3 Docker

Multi-stage build → `output: "standalone"`; the runtime image is just
`node server.js` + the standalone bundle. `NEXT_PUBLIC_*` is inlined at **build
time**, so `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` are passed as **build
args** in `docker-compose.yml` (the browser talks to the API on the host, hence
`localhost:8000` / `ws://localhost:8000`).

---

## 11. Containers & CI

### 11.1 `docker-compose.yml`

| service | image / build | notes |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | `schema.sql` mounted into the init dir; `pg_isready` healthcheck; `pg_data` volume |
| `api` | `./backend` | `env_file: backend/.env`; `DATABASE_URL` / `UPLOAD_DIR` / `CORS_ORIGINS` overridden; `uploads` volume at `/data/uploads`; waits on `postgres` healthy |
| `worker` | `./backend` | same image, `command: python -m app.worker`, healthcheck disabled, shares the `uploads` volume; waits on `postgres` healthy + `api` started |
| `web` | `./frontend` | build args inline the API/WS URLs; depends on `api` |

`api` and `worker` share the uploads volume because the worker reads the file the
API wrote by path (`documents.file_url`). Swapping to S3 + presigned URLs removes
that coupling.

### 11.2 `backend/Dockerfile`

`python:3.12-slim`; installs `tesseract-ocr`, `tesseract-ocr-hin`,
`poppler-utils`, `curl`; `pip install -r requirements.txt`; copies `app/`; runs
as a non-root `appuser`; `HEALTHCHECK` curls `/health`.

### 11.3 `.github/workflows/ci.yml` — on every push / PR to `main`

| job | steps |
|---|---|
| `backend` | pgvector service container → `pip install -r requirements-dev.txt` → `psql -f database/schema.sql` → `ruff check .` → `ruff format --check .` → `pytest -q` |
| `frontend` | `npm ci` → `npm run lint` → `npm run typecheck` → `npm run build` |
| `docker` | `cp backend/.env.example backend/.env` → `docker compose build` (all three images) |

`GROQ_API_KEY` in CI is a dummy — tests never call the LLM. No Kubernetes, no
registry push, no deploy step: this is a portfolio project and CI's job is "does
it still build and pass".

---

## 12. Testing — `backend/tests/`

FastAPI `TestClient` against a **real** pgvector Postgres.

- **`conftest.py`** sets env defaults, disables the progress listener, and
  probes the DB once. `requires_db` skips DB-backed tests cleanly when Postgres
  is unreachable, so `pytest` still runs the pure-logic tests anywhere. The `db`
  fixture `TRUNCATE … RESTART IDENTITY CASCADE`s all tables before and after each
  test; `auth_client` is a `TestClient` with a signed-up user's bearer token.
- **`test_auth.py`** — signup → login → me; duplicate email `409`; wrong password
  `401`; **refresh rotation** (old token burned, new one works); logout revokes;
  protected route rejects missing/garbage tokens.
- **`test_documents.py`** — upload → list; content-hash dedup; `415` on
  unsupported type; `process` enqueues a `queued` job and flips the document to
  `processing`; per-user isolation (`404` for another user's document); two users
  *can* upload the same bytes; stats shape (14-day window length, `by_status`).
- **`test_pipeline.py`** — pure logic, no DB, no network: chunk boundaries incl.
  Devanagari; sequential `chunk_index`; **LSA retrieval ranks the right chunk
  first** for four plain-English questions; every vector is exactly 256-d.
- **`test_health.py`** — `/health`.

LLM calls are never made in tests.

---

## 13. Deliberate trade-offs & upgrade paths

| today | why it's fine now | upgrade path |
|---|---|---|
| Retrieval: per-document TF-IDF → SVD (sklearn) | zero embeddings account/cost, deterministic, testable; corpora are tiny | swap `_build_transformer` / `_transform` for a hosted embedding model; bump `VECTOR(256)` + `DIM` together |
| LLM: Groq free tier | one key runs text + vision; fast | change `llm_client.py`; model ids already in `config.py` |
| File storage: shared Docker volume | one API replica, one worker | S3 + presigned upload URLs in `routers/documents.py`; drop the shared volume |
| Progress fan-out: in-process `_subscribers` registry | fine for one API replica | for many replicas, fan out purely through Postgres `NOTIFY` (already the transport) or Redis pub/sub |
| Queue: `jobs` table + `SKIP LOCKED` | a few documents at a time; retries + backoff already covered | Redis/BullMQ or SQS only when throughput actually demands it |
| Auth: email + password | simple, self-contained | add OAuth / phone OTP alongside the existing token scheme (unchanged) |
| Schema: `IF NOT EXISTS`, recreate-the-volume | no migration history to preserve yet | adopt Alembic before the first destructive change ships |
| No PII redaction | acceptable for a demo on public notices | redact Aadhaar / PAN before any text reaches the LLM (`simplify` / `qa` / `translate` inputs) |
| ivfflat `lists = 100` | <100 chunks/document, a handful of documents | tune toward `sqrt(row_count)`; consider HNSW |

### Before deploying anywhere

- Rotate `JWT_SECRET` and `GROQ_API_KEY`; never ship the dev defaults.
- Put the API behind TLS; lock `CORS_ORIGINS` to the real origin.
- Redact PII before sending document text to any LLM.

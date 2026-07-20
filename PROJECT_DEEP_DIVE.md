# Saral — Technical Project Document
### What Every Part Does, Why It Exists, and Why That Tool Over the Alternatives

This document goes one layer deeper than the README. The README tells you
*how to run the project*. This tells you *why the project is built the way
it is* — every service, every library, every architectural decision, and
what else was considered and rejected.

---

## 1. Design Philosophy

Three principles shaped every decision in this project:

1. **Separate the fast path from the slow path.** A user uploading a
   document and a user chatting about an already-processed document have
   completely different latency needs. Document processing (extraction,
   OCR, LLM calls) can take anywhere from 2 seconds to over a minute.
   Nothing in an HTTP request/response cycle should ever block on that.
   This single principle is why the project has a job queue and a
   separate worker process at all, instead of just running everything
   synchronously inside the API.

2. **The AI logic should live where the AI tooling is strongest.** Python
   has PyMuPDF, Tesseract bindings, tiktoken, and the entire LLM/NLP
   ecosystem. Node has none of that natively. Rather than fighting Node's
   weaker PDF/OCR libraries, the AI-heavy work is isolated into its own
   Python service, and the two languages talk over a plain internal HTTP
   API. This is a deliberate polyglot choice, not an accident.

3. **Every service should distrust its neighbors by default.** The AI
   service never talks to the internet-facing client directly — it only
   accepts requests carrying a shared internal token, so even if its port
   were accidentally exposed, it can't be called by anyone except
   `node-api`. This is a small thing that avoids a large class of
   mistakes later.

---

## 2. Why a Multi-Service Architecture (and not a monolith)

**What was considered:** a single Next.js app with API routes calling the
LLM directly, using Vercel's serverless functions or a similar model.

**Why it was rejected:** serverless functions have hard execution time
limits (often 10–60 seconds depending on platform/tier), and document
processing — extraction, OCR, an LLM call, embedding generation — can
comfortably exceed that for a multi-page scanned document. A background
worker pulling from a durable queue has no such ceiling; it can take as
long as it needs, and if it crashes mid-job, the job isn't silently lost
(BullMQ retries failed jobs rather than dropping them).

**What was built instead:** four independent processes — frontend, API
gateway, AI service, and a background worker — communicating over HTTP and
a shared Postgres/Redis backend. This also means each piece can be scaled
independently in production (e.g., running three AI-service replicas
behind a load balancer while running only one API gateway) — a monolith
can't do that at the process level.

---

## 3. Frontend — `web/`

### Next.js 14 (App Router) — *why not plain React (Vite/CRA) or Remix?*
Next.js was chosen for three concrete reasons specific to this project:
- **File-based routing** maps naturally onto the app's two real pages
  (landing/upload, document view) without hand-wiring a router.
- **Built-in TypeScript support** with zero config, matching the rest of
  the stack's type-safety goals.
- It's the framework most likely to be familiar to whoever maintains this
  next, given its dominant market position — a practical, not purely
  technical, reason.

Remix was a reasonable alternative (its loader/action model fits
polling-heavy UIs well) but was passed over because Next.js's App Router
ecosystem (component libraries, Tailwind integration, deployment tooling)
is more mature as of this build.

### TypeScript — *why not plain JavaScript?*
The frontend talks to three different backend response shapes (documents,
insights, chat messages) that change shape depending on processing status
and language. TypeScript's structural typing catches mismatches (e.g., a
component expecting `key_points: string[]` receiving a raw JSON string
from Postgres before it's parsed) at compile time instead of as a runtime
crash — which is exactly the class of bug that showed up during
development (`eligibility`/`key_points`/`deadlines` arriving as strings
from JSONB columns and needing explicit `JSON.parse`).

### Tailwind CSS — *why not styled-components, CSS Modules, or plain CSS?*
Utility-first CSS was chosen because the entire UI is componentized
(`SummaryCard`, `EligibilityChecklist`, `ChatWindow`, etc.) and Tailwind
lets each component's styling live directly next to its markup, with no
separate stylesheet to keep in sync. The custom design tokens (`teal`,
`amber`, `paper`/`ink` color scale, `Fraunces`/`Inter` type pairing) are
defined once in `tailwind.config.ts` and reused everywhere, avoiding the
"every component invents its own shade of blue" problem common in ad-hoc
CSS.

### lucide-react — *why not Font Awesome or a custom icon set?*
Tree-shakeable (only the icons actually imported end up in the bundle),
consistent stroke-based visual style, and no icon-font loading flash.
Chosen over Font Awesome specifically because Font Awesome's free tier is
solid-fill by default, which visually clashed with the softer,
line-icon-based design direction chosen for this app.

### `localStorage` for JWT — *why not httpOnly cookies?*
This is a genuine trade-off, not an oversight. `localStorage` was chosen
for development simplicity (no CORS/cookie-domain configuration needed
across `localhost:3000` and `localhost:4000`), but it is **more
vulnerable to XSS token theft** than an httpOnly cookie, since any
injected script can read `localStorage`. For a production deployment,
this should be swapped to an httpOnly, `SameSite=Strict` cookie issued by
`node-api`, which JavaScript can't read at all. This is flagged explicitly
so it isn't mistaken for a considered security decision — it's a
known-acceptable shortcut for local development only.

### Polling instead of WebSockets
Document status updates use a 3-second polling interval
(`setInterval` calling `GET /documents/:id`) rather than a WebSocket or
Server-Sent Events connection. WebSockets would reduce latency and
server load slightly, but for a process that takes 5–60 seconds either
way, the difference is imperceptible to the user, and polling avoids the
added complexity of managing persistent connections, reconnection logic,
and a stateful connection layer in the API gateway. This is the right
trade for this specific use case — it would **not** be the right choice
for something like live collaborative editing.

---

## 4. API Gateway — `node-api/`

### Express — *why not NestJS, Fastify, or staying in Next.js API routes?*
NestJS was seriously considered — it maps closely onto the plan's original
architecture and gives structured dependency injection, decorators, and
built-in validation pipelines. It was set aside in favor of Express for
one reason: **surface area**. This project's API gateway does five things
(auth, upload, document CRUD, chat proxy, queue enqueueing) — NestJS's
module/provider/controller scaffolding pays off on larger APIs with dozens
of resources and shared cross-cutting concerns, but on an API this size it
adds boilerplate without a matching benefit. Express keeps every route
readable in a single file, which matters more here than DI ergonomics.

Fastify (faster raw throughput than Express) was also considered and
rejected for the same reason in reverse — this app is not throughput-bound
by the API gateway; it's bound by LLM inference latency. Optimizing the
wrong bottleneck.

### JWT — *why not session cookies with server-side session storage?*
JWTs were chosen because they're **stateless** — `node-api` can verify a
token without a database round-trip or a shared session store, which
matters because the app already has multiple backend processes (the API
server and the worker) that would otherwise need to share session state.
The trade-off: JWTs can't be revoked before they expire (hence the short
15-minute expiry used here) without an additional denylist mechanism,
which a session-store approach gets "for free." For this project's scope,
short-lived tokens were judged sufficient.

### bcrypt — *why not argon2?*
argon2 is the more modern, more GPU-crack-resistant choice and would be
the better pick for a production deployment. bcrypt was used here because
it has zero native-compilation friction on Windows (a real, encountered
constraint during this project's development — several other Python
packages already caused native-build pain), and its security margin is
still considered adequate for this application's threat model. Flagged
as an easy, low-risk upgrade later (`bcryptjs` → `argon2` is a
drop-in-ish swap at the hashing call sites).

### multer + local disk — *why not direct-to-S3 presigned uploads?*
The plan's original target architecture uses presigned S3 URLs so large
files upload directly to object storage without ever passing through the
API server — the more scalable, more production-correct approach.
`multer` writing to local disk was used instead for one reason: **it
requires no cloud account, no credentials, and no billing setup** to run
the project locally. This was a deliberate simplification to keep the
project runnable by anyone with just a Groq key, at the direct cost of
not being suitable for a real multi-instance production deployment (local
disk storage doesn't work if you ever run more than one API server
instance, since uploaded files would only exist on whichever instance
received them).

### BullMQ + Redis — *why not a simpler `setTimeout`-based queue, or a heavier system like RabbitMQ/SQS?*
A naive alternative — just calling the AI service directly and `await`-ing
it inside the upload route — was rejected per the earlier "fast path vs.
slow path" principle. A truly heavyweight message broker (RabbitMQ, AWS
SQS) was also rejected as overkill: this app has one queue, one job type,
and no need for complex routing, dead-letter exchanges, or multi-consumer
fan-out. BullMQ sits at the right complexity point — it gives job
persistence, automatic retries on failure, and concurrency control, using
infrastructure (Redis) the project needs anyway for nothing else, without
requiring a dedicated broker service.

### SHA-256 file deduplication
Every uploaded file is hashed on arrival; if an identical file was already
processed, the existing result is returned instantly instead of
re-running the (costly, rate-limited) LLM pipeline. This matters
specifically because the app targets *government* documents — the same
scheme notice or form is likely to be uploaded by many different users
independently. Deduplication turns an O(n) cost (n = number of uploads)
into effectively O(unique documents).

---

## 5. AI Service — `fastapi-service/`

### FastAPI — *why not Flask or Django?*
FastAPI was chosen for three concrete, non-cosmetic reasons:
- **Native async support** matters here because the service calls out to
  an external LLM API (Groq) and a database on nearly every request —
  exactly the I/O-bound workload async is designed for.
- **Pydantic-based request validation** means every internal endpoint
  (`/internal/process`, `/internal/qa`, etc.) has its request shape
  enforced automatically, catching malformed calls from `node-api` before
  they reach business logic.
- **Auto-generated OpenAPI schema** (visible at `/docs` when running)
  gives free, always-accurate API documentation for the internal
  boundary, useful when debugging cross-service calls.

Django was never seriously in the running — its ORM, admin panel, and
templating system solve problems this service doesn't have; it would add
substantial unused weight.

### PyMuPDF (`fitz`) — *why not `pdfplumber` or `pypdf`?*
PyMuPDF was chosen for **extraction speed and per-page granularity**
(critical here, since the pipeline needs to decide *per page* whether
native text is sufficient or OCR fallback is needed). `pdfplumber` has
better table-extraction fidelity but is noticeably slower on large
documents. `pypdf` (formerly PyPDF2) has weaker text-extraction accuracy
on documents with complex layouts, which government forms frequently have
(multi-column layouts, embedded tables, watermarks). PyMuPDF was the best
fit for "fast, page-aware, good-enough-on-messy-layout" extraction.

### Tesseract + Poppler (OCR fallback) — *why OCR at all, and why this pair?*
Government documents are very often **scanned images** wrapped in a PDF
container — a photographed or photocopied form has zero extractable
native text, and PyMuPDF alone would return an empty string. The pipeline
checks per-page: if native extraction returns fewer than 40 characters,
it renders that page to an image (via `pdf2image`, which itself shells
out to **Poppler**'s `pdftoppm`) and runs Tesseract OCR on the image.
Tesseract was chosen over cloud OCR APIs (Google Vision, AWS Textract)
specifically to **keep the pipeline free and offline-capable** — no
per-page billing, no additional API key. The trade-off is accuracy:
Tesseract is noticeably weaker than commercial cloud OCR on low-quality
scans, skewed photographs, or non-Latin scripts beyond what its trained
language packs cover (this project ships with English + Hindi language
data; other Indian languages would need additional Tesseract language
packs installed).

### tiktoken for chunking — *why token-based instead of character-based splitting?*
Chunks are built to a target size in **tokens**, not characters, because
the LLM's context window and pricing are both token-denominated — a
character-based chunk size gives no reliable guarantee about how much of
the model's context budget a chunk will actually consume, especially
given that non-English text (Hindi, Kannada, etc.) tokenizes at a
different character-per-token ratio than English. `tiktoken` (originally
built for OpenAI's tokenizers) was used as a close-enough approximation
even though the project's LLM calls go to Groq's models — a perfectly
matched tokenizer isn't available for every open-weight model, and an
approximate token count is sufficient for chunk-sizing purposes, where
exact precision matters far less than staying safely under a limit.

### Groq — *why not Anthropic (Claude) or OpenAI, given the original plan specified Claude?*
This is a well-documented pivot in the project's own history: the app was
originally built against the **Anthropic API**, and the switch to **Groq**
was made specifically because Groq offers a genuinely free tier (no card,
no billing setup) sufficient for development and testing, whereas the
Anthropic account in use had no purchased credits. This is a **cost
decision, not a quality decision** — Groq's free-tier open-weight models
(`openai/gpt-oss-120b` by default) are noticeably less reliable than
Claude at strictly following "return only this JSON shape" instructions,
which is why `llm_client.py` includes an explicit retry-with-stricter-
instructions fallback that Claude never needed. The entire LLM
integration is isolated to one file (`llm_client.py`) specifically so
this swap — and any future swap back to Claude, or to OpenAI — only
requires changing that one file; every pipeline module (`simplify.py`,
`translate.py`, `qa.py`) calls generic `call_json()`/`call_text()`
functions and has no provider-specific code.

### Hashed bag-of-words "embeddings" — *why not a real embedding model?*
This is the most significant intentional shortcut in the project, and
it's worth explaining plainly: `embed.py` does not call any embedding API
at all. It hashes each word in a chunk into one of 1536 dimensions with a
sign determined by the hash, and normalizes the resulting vector. This
produces something that behaves *like* a sparse embedding for
nearest-neighbor search — documents sharing more of the same words will
have more similar vectors — but it has none of the semantic understanding
a real embedding model provides (it can't tell that "financial aid" and
"monetary assistance" are related concepts; it only matches on shared
vocabulary). This was chosen purely so the **entire application could run
on a single free API key**, with zero additional embedding-API cost or
signup. The code includes an explicit comment marking this as the first
thing to upgrade (to OpenAI's `text-embedding-3-large` or Voyage AI) for
any deployment where retrieval quality in the chat feature actually
matters.

### pgvector — *why not Pinecone, Weaviate, or Chroma?*
A dedicated vector database was in the original plan. It was replaced
with **pgvector**, a Postgres extension, for one reason: the project
already needs Postgres for every other piece of relational data (users,
documents, chat history) — running a second, separate vector database
would mean a second connection pool, a second piece of infrastructure to
deploy and monitor, and a second potential point of failure, for a
project whose actual vector search workload (searching within a single
document's chunks, typically well under 100 vectors) is nowhere near the
scale that justifies a dedicated vector database's specialized indexing.
pgvector's `<=>` cosine-distance operator, run directly against a
`vector` column, is functionally sufficient here and keeps the entire
data layer in one system.

---

## 6. Data Layer

### PostgreSQL — *why relational at all, given documents are semi-structured?*
The `document_insights` table stores structured fields (`summary`,
`explain_like_10`) alongside `JSONB` columns (`key_points`, `deadlines`,
`eligibility`) — a hybrid deliberately chosen because the data has both a
fixed, always-present shape (every document gets exactly one summary) and
a variable-depth shape (eligibility criteria vary wildly in structure
document to document). JSONB gives schema flexibility for the variable
parts while keeping the fixed parts (foreign keys, timestamps, unique
constraints like `(document_id, language)`) properly relational and
indexable — something a pure document database (MongoDB) would make
awkward for the relational parts (joining documents to users, chat
sessions to documents).

### Redis — *used for exactly one thing*
Redis in this project exists solely as BullMQ's backing store — it is not
used for caching API responses or session storage. Keeping its
responsibility singular makes the system easier to reason about: if Redis
is down, document *processing* stops, but logging in, viewing already-
processed documents, and browsing history all continue to work, since
none of those paths touch Redis.

---

## 7. Security Design — Rationale, Not Just Rules

| Mechanism | Why this, specifically |
|---|---|
| Shared `INTERNAL_SERVICE_TOKEN` between `node-api` and `fastapi-service` | The AI service has no user-facing auth of its own — it trusts nothing except a matching token, so it cannot be invoked by anyone who hasn't gone through `node-api`'s real authentication first, even if its port is reachable |
| Short-lived JWTs (15 min) | Limits the damage window of a stolen token, given the app has no revocation list |
| bcrypt password hashing | Passwords are never recoverable even from a full database leak |
| PDF-only, 50MB-capped uploads | Narrows the attack surface for upload-based exploits (arbitrary file execution, zip bombs, etc.) to a single, well-understood file format |
| `.gitignore` on all `.env` files | Prevents API keys and internal tokens from ever reaching version control by default, rather than relying on developer discipline alone |

---

## 8. What Was *Not* Built, and Why

Being explicit about scope boundaries is as important as documenting what
was built:

- **No Google OAuth / phone OTP** — email/password was sufficient to
  prove out the core document-processing flow; social/OTP auth is a
  separate, well-understood problem that doesn't change the app's core
  architecture, so it was deferred rather than built speculatively.
- **No voice (STT/TTS)** — genuinely valuable for the target audience
  (low-literacy users), but it's an entirely separate pipeline
  (audio capture, streaming transcription, TTS playback) that would
  roughly double the AI service's surface area; treated as a distinct
  future phase rather than bolted on incompletely.
- **No malware scanning on upload** — flagged explicitly as a pre-
  deployment requirement, not something skipped by oversight. Accepting
  arbitrary PDFs from the public internet without scanning is a real risk
  this project does not yet mitigate.
- **No PII redaction before LLM calls** — Indian government documents
  frequently contain Aadhaar/PAN numbers; sending that raw to any
  third-party LLM API is a real privacy concern that needs a redaction
  pass before this app should handle real citizens' documents in
  production.

---

## 9. Summary Table — Every Major Choice at a Glance

| Layer | Chosen | Alternatives considered | Deciding factor |
|---|---|---|---|
| Frontend framework | Next.js 14 | Vite+React, Remix | Routing fit + ecosystem maturity |
| Styling | Tailwind CSS | styled-components, CSS Modules | Component-colocated styling, shared design tokens |
| API gateway | Express | NestJS, Fastify | Surface area too small to justify NestJS's structure |
| Auth | JWT | Server-side sessions | Statelessness across multiple backend processes |
| Password hashing | bcrypt | argon2 | Zero native-build friction on Windows |
| File storage | Local disk (multer) | S3 presigned URLs | Runs with zero cloud account/billing setup |
| Job queue | BullMQ + Redis | Direct sync call, RabbitMQ/SQS | Right complexity point for one queue, one job type |
| AI service framework | FastAPI | Flask, Django | Async I/O fit + built-in validation |
| PDF extraction | PyMuPDF | pdfplumber, pypdf | Speed + per-page granularity |
| OCR | Tesseract + Poppler | Google Vision, AWS Textract | Free, offline, no per-page billing |
| Chunking unit | Tokens (tiktoken) | Characters | Matches LLM context/pricing reality |
| LLM provider | Groq | Anthropic (original), OpenAI | Free tier — zero billing to run/test |
| Embeddings | Hashed bag-of-words | OpenAI/Voyage embeddings | Zero additional API cost/signup |
| Vector search | pgvector (in Postgres) | Pinecone, Weaviate, Chroma | Avoids a second database for a small-scale workload |
| Relational DB | PostgreSQL (+ JSONB) | MongoDB | Fixed + variable-shape data mixed in one row, needs real joins |

---

*Every trade-off documented here was made deliberately to keep this
project runnable end-to-end on free infrastructure and a single free API
key, while preserving a real multi-service architecture. Each "upgrade
path" noted above is a scoped, isolated change — swapping any one of them
does not require touching the others.*

# Saral — AI Bureaucracy Simplifier

Phase 1 + Phase 2 of the plan, implemented and runnable: auth, PDF upload,
extraction (+OCR fallback), AI summarization, eligibility extraction, deadline
extraction, "explain like I'm 10", multilingual translation, and a RAG chat
that answers questions from the document only.

## Architecture
web (Next.js)  →  node-api (Express)  →  ai-service (FastAPI)
│                        │
postgres (+pgvector)      Anthropic API
│
redis + BullMQ (async processing queue)

- **web/** — Next.js frontend (upload, result dashboard, chat).
- **node-api/** — Express API: auth (JWT), document CRUD, upload handling,
  enqueues processing jobs, proxies chat to the AI service. Also runs the
  BullMQ **worker** that drives the pipeline.
- **fastapi-service/** — the AI-heavy work: PDF/OCR extraction, chunking,
  embeddings (stored in Postgres via `pgvector`), the batched
  summarize/eligibility/ELI10 LLM call, translation, and RAG Q&A.
- **database/schema.sql** — auto-applied to Postgres on first boot.

## 1. Get an Anthropic API key

You'll need one before anything will actually generate summaries:
1. Go to https://console.anthropic.com/settings/keys
2. Create a key (you may need to add billing details first)
3. Copy it — you'll paste it into `fastapi-service/.env` below

## 2. Configure environment variables

cp fastapi-service/.env.example fastapi-service/.env
cp node-api/.env.example node-api/.env

Edit `fastapi-service/.env` and paste your key: `ANTHROPIC_API_KEY=sk-ant-...`

In both `.env` files, set `INTERNAL_SERVICE_TOKEN` to the **same** random
string (shared secret between node-api and the AI service). Generate one with:
`openssl rand -hex 32`
Also set `JWT_SECRET` in `node-api/.env` to another random string.

## 3. Run everything with Docker

docker compose up --build

Then open http://localhost:3000 (Node API: :4000/health, AI service: :8000/health)

## 4. Running without Docker (local dev)

Postgres + Redis: `docker compose up postgres redis`

AI service:
cd fastapi-service && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

Node API + worker (two terminals):
cd node-api && npm install
npm run dev       # terminal 1
npm run worker    # terminal 2

Frontend:
cd web && npm install && npm run dev

## How a document flows through the system

1. User signs up / logs in (JWT).
2. Upload PDF → saved to disk (swap for S3 signed URLs before deploying), deduped by SHA-256 hash.
3. `POST /documents/:id/process` enqueues a BullMQ job.
4. Worker calls `/internal/process`: extract (+OCR) → one batched Claude call
   for summary/eligibility/deadlines/ELI10 → chunk + embed into pgvector.
5. Frontend polls `GET /documents/:id` until `status = ready`.
6. Switching language calls `/documents/:id/translate`, cached per (document_id, language).
7. Chat retrieves top-5 relevant chunks and asks Claude to answer only from that context.

## Known trade-offs (see comments in code for how to upgrade)

- Embeddings: free hashed bag-of-words vector, not a real embedding model — swap in OpenAI/Voyage later.
- File storage: local disk instead of S3 — swap multer config before deploying.
- Auth: email/password only, no Google OAuth/phone-OTP yet.
- Voice (STT/TTS): not implemented — Phase 3.
- PWA offline caching: manifest.json is in place; add next-pwa for the service worker.

## Security notes before deploying

- Rotate `JWT_SECRET` and `INTERNAL_SERVICE_TOKEN`.
- Keep `ai-service` internal-only, never public.
- Add malware scanning + PII redaction (Aadhaar/PAN) before sending text to the LLM.
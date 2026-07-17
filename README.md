# 🗂️ Saral — सरल, Simplified

> *Saral* means "simple" in Hindi. That's the whole pitch: take a government
> document nobody wants to read, and make it make sense.

Upload a PDF of a government scheme, notice, or form. Get back a plain-language
summary, an eligibility checklist, key deadlines, an "explain it like I'm 10"
version — in your language — and a chatbot that answers questions using
*only* what's actually in the document, not guesses.

Built as a real multi-service architecture, not a toy: separate frontend,
API gateway, AI service, job queue, and vector search — because that's what
it takes to process documents asynchronously without blocking anyone.

---

## 🏗️ How it's wired together
Next.js (web)
│
▼
Express API (node-api) ──── BullMQ + Redis (job queue)
│                            │
▼                            ▼
Postgres + pgvector      FastAPI (ai-service) ──── Groq API

| Piece | What it does |
|---|---|
| **`web/`** | Next.js frontend — upload, live status, summary/eligibility cards, chat |
| **`node-api/`** | Express: auth (JWT), uploads, dedup by file hash, enqueues jobs, chat proxy. Also runs the **worker** that drives the whole pipeline |
| **`fastapi-service/`** | The actual AI work: PDF/OCR extraction, chunking, embeddings (pgvector), the summarize/eligibility/ELI10 call, translation, RAG Q&A |
| **`database/schema.sql`** | Applied automatically to Postgres on first boot |

Everything talks over plain HTTP internally, guarded by a shared internal
token — no service trusts another blindly.

---

## ⚡ Get it running

### 1. Get a free Groq API key
This app runs entirely on **Groq's free tier** — no card, no billing, no
waiting on trial credits.
→ https://console.groq.com/keys — sign in, create a key, copy it.

### 2. Set up your environment files

```bash
cp fastapi-service/.env.example fastapi-service/.env
cp node-api/.env.example node-api/.env
```

Fill in `fastapi-service/.env`:
GROQ_API_KEY=gsk_your_real_key_here
INTERNAL_SERVICE_TOKEN=<generate below>
DATABASE_URL=postgresql://bureaucracy:bureaucracy@localhost:5432/bureaucracy

Generate a proper random token (don't hand-type one):
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste the same value into **both** `fastapi-service/.env` and
`node-api/.env` — these two services check that they match on every
internal call. Also set a separate `JWT_SECRET` in `node-api/.env`.

> ⚠️ **Windows PowerShell users:** if you write `.env` files with
> `Set-Content -Encoding utf8`, PowerShell silently adds a BOM (byte-order
> mark) that breaks env parsing in subtle, confusing ways. Use
> `-Encoding ascii` instead, or edit the file directly in VS Code.

### 3. Run it — Docker (easiest)

```bash
docker compose up --build
```

→ **http://localhost:3000**
(Node API health: `:4000/health` · AI service health: `:8000/health`)

### 4. Run it — locally, no Docker

You'll still want Postgres + Redis in Docker:
```bash
docker compose up postgres redis
```

**AI service:**
```bash
cd fastapi-service
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

**Node API + worker** (two separate terminals — the worker is what
actually processes documents, nothing happens without it running):
```bash
cd node-api
npm install
npm run dev       # terminal 1 — the HTTP API
npm run worker    # terminal 2 — the processing worker
```

**Frontend:**
```bash
cd web
npm install
npm run dev
```

### 5. Enable OCR (optional, but recommended)

Plenty of real-world government documents are scanned images, not
selectable text. Without OCR tooling, those come back with an empty
summary. To support them, install two system tools and put them on PATH:

- **Tesseract**: https://github.com/UB-Mannheim/tesseract-ocr-w64-setup — during install, add the **Hindi** language pack too
- **Poppler**: https://github.com/oschwartz10612/poppler-windows/releases/latest

Verify both are visible after a full terminal/editor restart:
```bash
tesseract --version
pdftoppm -v
```
If either command isn't found, extraction silently falls back to
native-text-only — the app won't crash, but scanned PDFs will summarize
as empty.

---

## 🔁 What happens when you upload a document

1. Sign up / log in → JWT issued.
2. Upload a PDF → saved to disk, deduplicated by SHA-256 hash (upload the
   same file twice, get the same result instantly, no reprocessing).
3. `POST /documents/:id/process` → job dropped onto the BullMQ queue.
4. The worker calls the AI service's `/internal/process`:
   extract (+ OCR fallback) → one batched LLM call for
   summary/eligibility/deadlines/ELI10 → chunk + embed into `pgvector`.
5. Frontend polls until `status = ready`.
6. Switching language hits `/documents/:id/translate` — cached per
   `(document_id, language)`, so the same document only gets translated
   once no matter how many people view it.
7. Chat retrieves the top-5 most relevant chunks via vector similarity and
   asks the model to answer strictly from that context — no hallucinated
   eligibility rules.

---

## 🧭 Deliberate trade-offs (and how to graduate past them)

| Today | Production upgrade path |
|---|---|
| LLM: Groq free tier (open-weight models) | Swap `fastapi-service/app/llm_client.py` for Claude/GPT if you need stronger instruction-following |
| Embeddings: hashed bag-of-words (zero-dependency, runs free) | Swap `embed.py` for OpenAI/Voyage embeddings — meaningfully better retrieval |
| File storage: local disk | Swap the `multer` config in `documents.js` for S3 presigned URLs |
| Auth: email + password only | Add Google OAuth / phone OTP |
| Voice (STT/TTS) | Not built yet — natural Phase 3 |
| PWA: manifest is in place | Add `next-pwa` for real offline support |

---

## 🔒 Before you actually deploy this anywhere

- Rotate `JWT_SECRET` and `INTERNAL_SERVICE_TOKEN` — never reuse dev values
- Keep `ai-service` off the public internet entirely — it should only be
  reachable from `node-api`
- Add malware scanning and PII redaction (Aadhaar/PAN patterns) on upload
  before any document text reaches the LLM
- If you ever paste an API key into a chat, a doc, or a commit by
  accident — rotate it. Assume it's burned.

---

Built messily, debugged relentlessly, works now. 🎉

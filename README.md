# 🗂️ Saral — सरल, Simplified

> *Saral* means "simple" in Hindi. That's the whole pitch: take a government
> document nobody wants to read, and make it make sense.

Upload a PDF of a government scheme, notice, or form. Get back a plain-language
summary, an eligibility checklist, key deadlines, an "explain it like I'm 10"
version — in your language — and a chatbot that answers questions using
*only* what's actually in the document, not guesses.

---

## 🏗️ How it's wired together

```
   Next.js (web)
        │
        ▼
  Express API (node-api) ──── BullMQ + Redis (job queue)
        │                            │
        ▼                            ▼
   Postgres + pgvector      FastAPI (ai-service) ──── Groq API
```

| Piece | What it does |
|---|---|
| **`web/`** | Next.js frontend — upload, live status, summary/eligibility cards, chat |
| **`node-api/`** | Express: auth (JWT), uploads, dedup by file hash, enqueues jobs, chat proxy. Also runs the **worker** that drives the whole pipeline |
| **`fastapi-service/`** | The actual AI work: PDF/OCR extraction, chunking, embeddings (pgvector), the summarize/eligibility/ELI10 call, translation, RAG Q&A |
| **`database/schema.sql`** | Applied automatically to Postgres on first boot |

For a deep dive into *why* each tool was chosen, see `PROJECT_DEEP_DIVE.md`.

---

## ✅ Requirements (all OSes)

- **Docker Desktop** (or Docker Engine + Compose on Linux)
- **Node.js 20+**
- **Python 3.11 or 3.12** — not 3.14; some packages (`pymupdf`) don't have
  prebuilt wheels for it yet and will fail to install
- A **free Groq API key** → https://console.groq.com/keys (no card required)

---

## ⚡ Option A — Docker only (same commands on every OS)

This is the fastest path and the only section that's genuinely identical
across Windows, macOS, and Linux, since Docker abstracts the OS away.

```bash
git clone https://github.com/praarn/bureaucracySimplifier.git
cd bureaucracySimplifier

cp fastapi-service/.env.example fastapi-service/.env
cp node-api/.env.example node-api/.env
```

Edit both `.env` files (see **Step 2** under Option B below for exactly
what to fill in), then:

```bash
docker compose up --build
```

→ **http://localhost:3000**

---

## ⚡ Option B — Running each service natively (recommended while developing)

Commands are grouped by OS starting at **Step 3**, since setup (Steps 1–2)
is identical everywhere.

### Step 1 — Clone and enter the project (all OSes)

```bash
git clone https://github.com/praarn/bureaucracySimplifier.git
cd bureaucracySimplifier
```

### Step 2 — Create and fill in environment files (all OSes)

```bash
cp fastapi-service/.env.example fastapi-service/.env
cp node-api/.env.example node-api/.env
```

Generate a random internal token — **use the same value in both files**:

**Windows (PowerShell):**
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

**macOS / Linux:**
```bash
openssl rand -hex 32
```

Open `fastapi-service/.env` and fill in:
```
GROQ_API_KEY=gsk_your_real_key_here
INTERNAL_SERVICE_TOKEN=<paste the generated token>
DATABASE_URL=postgresql://bureaucracy:bureaucracy@localhost:5432/bureaucracy
EMBEDDING_PROVIDER=local
```

Open `node-api/.env` and fill in (same `INTERNAL_SERVICE_TOKEN` value):
```
DATABASE_URL=postgresql://bureaucracy:bureaucracy@localhost:5432/bureaucracy
REDIS_URL=redis://localhost:6379
AI_SERVICE_URL=http://localhost:8000
INTERNAL_SERVICE_TOKEN=<same token as above>
JWT_SECRET=<another random string, same method as above>
UPLOAD_DIR=./uploads
PORT=4000
```

> ⚠️ **Windows PowerShell users only:** if you write these files using
> `Set-Content -Encoding utf8`, PowerShell silently adds a BOM that breaks
> env parsing. If you script the file creation instead of pasting in an
> editor, use `-Encoding ascii` instead.

---

### Step 3 — Start Postgres + Redis (all OSes, identical)

Open **Terminal 1** and leave it running:
```bash
docker compose up postgres redis
```
Wait ~10 seconds for it to fully initialize before continuing.

---

### Step 4 — Start the AI service

Open **Terminal 2**.

**Windows (PowerShell):**
```powershell
cd fastapi-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

**macOS / Linux:**
```bash
cd fastapi-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Confirm it's up: open `http://localhost:8000/health` — should show
`{"status":"ok"}`.

> **Optional — enable OCR for scanned PDFs.** Without this, scanned/
> image-only documents will extract as empty text.
> - **Windows:** install [Tesseract](https://github.com/UB-Mannheim/tesseract-ocr-w64-setup) (check the Hindi language pack during install) and [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/latest), then add both installation `bin` folders to your PATH and fully restart your terminal.
> - **macOS:** `brew install tesseract tesseract-lang poppler`
> - **Linux (Debian/Ubuntu):** `sudo apt install tesseract-ocr tesseract-ocr-hin poppler-utils`
>
> Verify with `tesseract --version` and `pdftoppm -v` on any OS.

---

### Step 5 — Start the Node API

Open **Terminal 3** (same commands on every OS):
```bash
cd node-api
npm install
npm run dev
```

Confirm: `http://localhost:4000/health`.

---

### Step 6 — Start the background worker

Open **Terminal 4** — **this must be running before you upload anything**,
or documents will sit stuck at "processing" forever (same commands on
every OS):
```bash
cd node-api
npm run worker
```

You should see:
```
[worker] listening for document-processing jobs
```

---

### Step 7 — Start the frontend

Open **Terminal 5** (same commands on every OS):
```bash
cd web
npm install
npm run dev
```

→ **http://localhost:3000**

---

## 🔁 Every time you come back to work on it (after the first setup)

You don't need to repeat `npm install` / `pip install` again unless
`package.json` or `requirements.txt` changed. Just re-run the five start
commands in order, one per terminal:

```bash
# Terminal 1
docker compose up postgres redis

# Terminal 2 — Windows
cd fastapi-service && .venv\Scripts\activate && uvicorn app.main:app --port 8000
# Terminal 2 — macOS/Linux
cd fastapi-service && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 3
cd node-api && npm run dev

# Terminal 4
cd node-api && npm run worker

# Terminal 5
cd web && npm run dev
```

---

## 🧹 Resetting stuck/broken documents

If a document gets stuck at `processing` (e.g. the worker wasn't running
when it was uploaded), clear it out — same command on every OS since it
runs inside the Docker container regardless of host OS:

```bash
docker exec -it bureaucracysimplifier-postgres-1 psql -U bureaucracy -d bureaucracy -c "DELETE FROM documents;"
```

---

## 🛑 Shutting everything down

Ctrl+C in Terminals 2–5, then in Terminal 1:
```bash
docker compose down
```
Add `-v` to also wipe the database (`docker compose down -v`) if you want
a completely clean slate next time.

---

## 🔁 What happens when you upload a document

1. Sign up / log in → JWT issued.
2. Upload a PDF → saved to disk, deduplicated by SHA-256 hash.
3. `POST /documents/:id/process` → job dropped onto the BullMQ queue.
4. The worker calls the AI service: extract (+ OCR fallback) → one
   batched LLM call for summary/eligibility/deadlines/ELI10 → chunk +
   embed into `pgvector`.
5. Frontend polls until `status = ready`.
6. Switching language calls `/documents/:id/translate`, cached per
   `(document_id, language)`.
7. Chat retrieves the top-5 relevant chunks and asks the LLM to answer
   only from that context.

---

## 🧭 Deliberate trade-offs

| Today | Production upgrade path |
|---|---|
| LLM: Groq free tier | Swap `fastapi-service/app/llm_client.py` for Claude/GPT |
| Embeddings: hashed bag-of-words | Swap `embed.py` for OpenAI/Voyage embeddings |
| File storage: local disk | Swap `multer` config in `documents.js` for S3 presigned URLs |
| Auth: email/password only | Add Google OAuth / phone OTP |
| Voice (STT/TTS) | Not implemented — Phase 3 |
| PWA offline caching | manifest.json is in place; add `next-pwa` for a service worker |

See `PROJECT_DEEP_DIVE.md` for the full reasoning behind every choice above.

---

## 🔒 Before you deploy this anywhere

- Rotate `JWT_SECRET` and `INTERNAL_SERVICE_TOKEN` — never reuse dev values
- Keep `ai-service` off the public internet — only `node-api` should reach it
- Add malware scanning + PII redaction (Aadhaar/PAN) before sending document text to the LLM
- If an API key or token is ever pasted somewhere public by accident — rotate it immediately

---

Built messily, debugged relentlessly, works now. 🎉

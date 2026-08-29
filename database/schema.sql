-- Parchi — core schema
-- Applied automatically by docker-compose (mounted into the postgres init dir).
-- To re-apply against an existing volume, see commands.md ("Database").

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector; -- pgvector: keeps vector search local + free, no Pinecone

-- ---------------------------------------------------------------------------
-- Users & auth
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    preferred_language TEXT DEFAULT 'en',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Opaque refresh tokens (the access token is a stateless short-lived JWT and is
-- never stored). Only the sha256 of the token is kept, so a DB leak can't be
-- replayed. Rotation: /auth/refresh revokes the presented row and inserts a new
-- one; /auth/logout just revokes.
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Documents & pipeline output
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    file_url TEXT NOT NULL,          -- path on the shared uploads volume
    file_hash TEXT,                  -- sha256 of the bytes; used for per-user dedup
    mime_type TEXT,                  -- application/pdf | image/png | image/jpeg | image/webp
    original_filename TEXT,
    status TEXT DEFAULT 'uploaded',  -- uploaded | processing | ready | failed
    -- Real per-stage progress written by the worker as it runs the pipeline:
    -- extracting | vision | simplifying | embedding | tables | finalizing | failed.
    -- The frontend shows this instead of a cosmetic timer.
    processing_stage TEXT,
    -- Set when status flips to 'processing'; the worker's stuck-job sweep uses it
    -- to fail documents that have been processing far too long (e.g. the worker
    -- was down when the job was enqueued).
    processing_started_at TIMESTAMPTZ,
    page_count INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    -- Dedup is per user: two people may upload the same public notice, but one
    -- person re-uploading a file they already have short-circuits.
    UNIQUE (user_id, file_hash)
);

-- Raw per-page extracted text. Persisted so it survives past a single pipeline
-- run (re-chunking, debugging a bad summary, re-OCR of one page) without
-- re-reading the source file.
CREATE TABLE IF NOT EXISTS document_text (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT,
    content TEXT
);

CREATE TABLE IF NOT EXISTS document_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    language TEXT DEFAULT 'en',
    summary TEXT,
    key_points JSONB,
    deadlines JSONB,
    eligibility JSONB,
    explain_like_10 TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, language)
);

-- Structured tables lifted out of the document (fee schedules, income slabs,
-- etc.) via PyMuPDF -> pandas. One row per detected table.
CREATE TABLE IF NOT EXISTS document_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT,
    data JSONB,          -- { "columns": [...], "rows": [[...], ...] }
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Retrieval (RAG)
-- ---------------------------------------------------------------------------

-- 256-dim dense vectors produced by a per-document TF-IDF + TruncatedSVD (LSA)
-- pipeline in app/pipeline/embed.py. Deterministic, no embeddings API/account.
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT,
    page_number INT,
    text TEXT,
    embedding VECTOR(256)
);

-- The fitted (TfidfVectorizer, TruncatedSVD) pair for a document, pickled, so a
-- later question can be projected into exactly the same vector space the chunks
-- were embedded in.
CREATE TABLE IF NOT EXISTS document_vectorizers (
    document_id UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    payload BYTEA NOT NULL,
    n_components INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Chat
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT, -- user | assistant
    content TEXT,
    language TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Background jobs (Postgres-backed queue; no Redis)
-- ---------------------------------------------------------------------------
--
-- The worker claims work with:
--   SELECT ... FROM jobs
--    WHERE status = 'queued' AND run_after <= now()
--    ORDER BY created_at
--    FOR UPDATE SKIP LOCKED
--    LIMIT 1;
-- SKIP LOCKED lets multiple workers run without double-processing a job.
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    type TEXT NOT NULL DEFAULT 'process-document',
    status TEXT NOT NULL DEFAULT 'queued', -- queued | running | done | failed
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_document ON embeddings(document_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(status, run_after, created_at);
CREATE INDEX IF NOT EXISTS idx_document_tables_document ON document_tables(document_id);

-- Approximate-nearest-neighbour index for the cosine search in
-- embed.py::retrieve_top_chunks(). Harmless at this project's scale (a handful of
-- documents, <100 chunks each) but it's the first thing retrieval would need to
-- stay fast on a large corpus. lists=100 suits small-to-medium row counts; for a
-- big corpus tune it toward sqrt(row_count).
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

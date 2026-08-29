# database/ — schema notes

`schema.sql` is the whole schema. Docker mounts it into the Postgres image's
init directory, so it runs **once**, when the `pg_data` volume is first created.
Everything is `CREATE … IF NOT EXISTS`, so re-applying it by hand against an
existing database is safe (see `commands.md`). There is no migration tool — the
project is small enough that "recreate the volume" is the reset story.

Requires the `vector` (pgvector) and `pgcrypto` extensions — both ship in the
`pgvector/pgvector:pg16` image.

## Tables

| table | notes |
|-------|-------|
| `users` | bcrypt hash in `password_hash` |
| `refresh_tokens` | only the **sha256** of each refresh token; `revoked_at` for rotation/logout |
| `documents` | `status` + `processing_stage` drive the UI; `UNIQUE (user_id, file_hash)` makes dedup **per user** (two people may upload the same public notice) |
| `document_text` | raw per-page text, persisted so it can be reused without re-reading the file |
| `document_insights` | one row per `(document, language)` — the English row is written by the pipeline, others by cached translations |
| `document_tables` | tables lifted out by `pipeline/tables.py`, as `{columns, rows}` JSON |
| `embeddings` | `VECTOR(256)` — LSA vectors from `pipeline/embed.py`; ivfflat cosine index |
| `document_vectorizers` | the pickled `(TF-IDF, SVD)` transformer per document, so questions land in the same vector space as the chunks |
| `chat_sessions` / `chat_messages` | one session per `(document, user)`; full turn history |
| `jobs` | the background queue — claimed with `FOR UPDATE SKIP LOCKED`; `attempts` / `max_attempts` / `run_after` drive retry-with-backoff |

## Why `VECTOR(256)`

The retrieval embeddings are a per-document TF-IDF → TruncatedSVD projection
(`pipeline/embed.py`), not a hosted model. 256 dims is plenty for documents with
well under a few hundred chunks and keeps the ivfflat index small. Changing the
embedding method means changing this number and `DIM` in `embed.py` together.

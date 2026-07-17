import hashlib
import math
import os
import re

import psycopg
from pgvector.psycopg import register_vector

DIM = 1536


def _get_conn():
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    register_vector(conn)
    return conn


def embed_text(text: str) -> list[float]:
    """Deterministic hashed bag-of-words embedding.

    This has no external dependency and no API cost, so the whole app runs
    with just an ANTHROPIC_API_KEY. Retrieval quality is 'good enough' for
    keyword-ish matching but noticeably weaker than a real embedding model.
    To upgrade: set EMBEDDING_PROVIDER=openai and swap this function for a
    call to OpenAI's text-embedding-3-large (or Voyage AI), keeping DIM in
    sync with database/schema.sql.
    """
    vector = [0.0] * DIM
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    for word in words:
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        idx = h % DIM
        sign = 1.0 if (h // DIM) % 2 == 0 else -1.0
        vector[idx] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def embed_and_store(document_id: str, chunks: list[dict]) -> int:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM embeddings WHERE document_id = %s", (document_id,))
            for chunk in chunks:
                vector = embed_text(chunk["text"])
                cur.execute(
                    """
                    INSERT INTO embeddings (document_id, chunk_index, page_number, text, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (document_id, chunk["chunk_index"], chunk["page_number"], chunk["text"], vector),
                )
    return len(chunks)


def retrieve_top_chunks(document_id: str, question: str, top_k: int = 5) -> list[dict]:
    q_vector = embed_text(question)
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_number, text
                FROM embeddings
                WHERE document_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (document_id, q_vector, top_k),
            )
            rows = cur.fetchall()
    return [{"page_number": r[0], "text": r[1]} for r in rows]
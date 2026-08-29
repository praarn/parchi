"""Database access.

A single process-wide psycopg connection pool. Every connection gets pgvector's
type adapters registered so ``VECTOR`` columns round-trip as Python lists /
numpy arrays.

The pool is opened lazily on first use and closed from the FastAPI lifespan (and
from the worker's shutdown path).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

_pool: ConnectionPool | None = None


def _configure(conn: psycopg.Connection) -> None:
    conn.autocommit = True
    # libpq can otherwise pick up the host's ANSI codepage on Windows, which
    # mangles any non-ASCII text (curly quotes, ₹, Devanagari) on the way out.
    conn.execute("SET client_encoding TO 'UTF8'")
    register_vector(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "client_encoding": "UTF8"},
            configure=_configure,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def cursor() -> Iterator[psycopg.Cursor]:
    """Borrow a connection from the pool and yield a dict-row cursor."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            yield cur


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> None:
    with cursor() as cur:
        cur.execute(sql, params)


# ---------------------------------------------------------------------------
# Pipeline helpers (previously lived in a private copy inside embed.py)
# ---------------------------------------------------------------------------


def store_document_text(document_id: str, pages: list[dict]) -> None:
    """Persist per-page extracted text into ``document_text``.

    Kept separate from the pipeline so the raw text survives a single run and
    can be reused (re-chunking, debugging, per-page re-OCR) without re-reading
    the source file.
    """
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_text WHERE document_id = %s", (document_id,))
            for page in pages:
                cur.execute(
                    "INSERT INTO document_text (document_id, page_number, content) VALUES (%s, %s, %s)",
                    (document_id, page["page_number"], page["text"]),
                )


def update_processing_stage(document_id: str, stage: str) -> None:
    """Write real pipeline progress into ``documents.processing_stage`` and fire a
    ``NOTIFY`` so any WebSocket subscriber gets pushed the update immediately."""
    payload = json.dumps({"document_id": str(document_id), "stage": stage})
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET processing_stage = %s WHERE id = %s",
                (stage, document_id),
            )
            cur.execute("SELECT pg_notify('parchi_progress', %s)", (payload,))


def notify_status(document_id: str, status: str, stage: str | None = None) -> None:
    """Fire a progress NOTIFY when the document's top-level status changes
    (``ready`` / ``failed``) so subscribers can close out."""
    payload = json.dumps({"document_id": str(document_id), "status": status, "stage": stage})
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_notify('parchi_progress', %s)", (payload,))

"""A tiny Postgres-backed job queue.

Replaces the old Redis/BullMQ setup. One table (``jobs``), claimed with
``FOR UPDATE SKIP LOCKED`` so any number of worker processes can run side by
side without ever handing the same job to two of them.

Retries: a failed attempt is re-queued with exponential backoff
(``run_after = now() + 5s * 2**attempts``) until ``max_attempts`` is reached,
after which the job is marked ``failed`` for good.
"""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import settings
from app.db import cursor

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def enqueue(document_id: str, job_type: str = "process-document") -> dict[str, Any]:
    """Add a job (and reset any stale one for this document)."""
    with cursor() as cur:
        cur.execute(
            "DELETE FROM jobs WHERE document_id = %s AND status IN ('queued', 'failed')",
            (document_id,),
        )
        cur.execute(
            """
            INSERT INTO jobs (document_id, type, max_attempts)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (document_id, job_type, settings.job_max_attempts),
        )
        return cur.fetchone()


def claim_next() -> dict[str, Any] | None:
    """Atomically claim the oldest runnable job, or return None."""
    with cursor() as cur:
        cur.execute(
            """
            WITH next AS (
                SELECT id FROM jobs
                 WHERE status = 'queued' AND run_after <= now()
                 ORDER BY created_at
                 FOR UPDATE SKIP LOCKED
                 LIMIT 1
            )
            UPDATE jobs j
               SET status = 'running',
                   attempts = j.attempts + 1,
                   locked_at = now(),
                   locked_by = %s,
                   updated_at = now()
              FROM next
             WHERE j.id = next.id
            RETURNING j.*
            """,
            (WORKER_ID,),
        )
        return cur.fetchone()


def complete(job_id: str) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status = 'done', updated_at = now(), last_error = NULL WHERE id = %s",
            (job_id,),
        )


def fail(job: dict[str, Any], error: str) -> bool:
    """Record a failed attempt. Returns True if the job is permanently failed
    (no retries left), False if it was re-queued for another attempt."""
    attempts = job["attempts"]
    max_attempts = job["max_attempts"]
    permanent = attempts >= max_attempts
    with cursor() as cur:
        if permanent:
            cur.execute(
                "UPDATE jobs SET status = 'failed', last_error = %s, updated_at = now() WHERE id = %s",
                (error[:2000], job["id"]),
            )
        else:
            backoff = timedelta(seconds=5 * (2**attempts))
            cur.execute(
                """
                UPDATE jobs
                   SET status = 'queued',
                       run_after = %s,
                       last_error = %s,
                       locked_at = NULL,
                       locked_by = NULL,
                       updated_at = now()
                 WHERE id = %s
                """,
                (datetime.now(UTC) + backoff, error[:2000], job["id"]),
            )
    return permanent


def sweep_stuck() -> int:
    """Fail documents left at ``processing`` far longer than any real run takes
    (e.g. the worker was down when the job was enqueued and the job row was
    lost). Returns how many were swept."""
    threshold = settings.worker_stuck_threshold_minutes
    with cursor() as cur:
        cur.execute(
            f"""
            UPDATE documents
               SET status = 'failed', processing_stage = 'failed'
             WHERE status = 'processing'
               AND processing_started_at IS NOT NULL
               AND processing_started_at < now() - interval '{threshold} minutes'
            RETURNING id
            """
        )
        return len(cur.fetchall())

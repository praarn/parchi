"""Background worker.

Polls the Postgres ``jobs`` queue and runs the full document pipeline:

    extracting -> simplifying -> embedding -> tables -> finalizing

Each stage writes ``documents.processing_stage`` and fires a NOTIFY, so the
frontend's WebSocket shows real progress. Failures are retried by the queue with
backoff; once retries are exhausted the document is marked ``failed``.

Run: ``python -m app.worker``
"""

from __future__ import annotations

import json
import logging
import signal
import time
import traceback

from app.config import settings
from app.db import (
    close_pool,
    cursor,
    get_pool,
    notify_status,
    store_document_text,
    update_processing_stage,
)
from app.pipeline.chunk import chunk_pages
from app.pipeline.embed import embed_and_store
from app.pipeline.extract import extract_text
from app.pipeline.simplify import simplify_document
from app.pipeline.tables import extract_tables
from app.queue import claim_next, complete, fail, sweep_stuck

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
log = logging.getLogger("parchi.worker")

_running = True


def _stop(signum, _frame):
    global _running
    log.info("received signal %s, finishing current job then exiting", signum)
    _running = False


def _store_tables(document_id: str, tables: list[dict]) -> None:
    with cursor() as cur:
        cur.execute("DELETE FROM document_tables WHERE document_id = %s", (document_id,))
        for t in tables:
            cur.execute(
                "INSERT INTO document_tables (document_id, page_number, data) VALUES (%s, %s, %s)",
                (document_id, t["page_number"], json.dumps(t["data"])),
            )


def _upsert_insight(document_id: str, insight: dict) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_insights
                (document_id, language, summary, key_points, deadlines, eligibility, explain_like_10)
            VALUES (%s, 'en', %s, %s, %s, %s, %s)
            ON CONFLICT (document_id, language) DO UPDATE SET
                summary = EXCLUDED.summary,
                key_points = EXCLUDED.key_points,
                deadlines = EXCLUDED.deadlines,
                eligibility = EXCLUDED.eligibility,
                explain_like_10 = EXCLUDED.explain_like_10
            """,
            (
                document_id,
                insight.get("summary"),
                json.dumps(insight.get("key_points", [])),
                json.dumps(insight.get("deadlines", [])),
                json.dumps(insight.get("eligibility", {})),
                insight.get("explain_like_10"),
            ),
        )


def process_document(job: dict) -> None:
    document_id = str(job["document_id"])
    with cursor() as cur:
        cur.execute("SELECT file_url, mime_type FROM documents WHERE id = %s", (document_id,))
        doc = cur.fetchone()
    if doc is None:
        log.warning("job %s references a missing document; dropping", job["id"])
        complete(job["id"])
        return

    file_url, mime_type = doc["file_url"], doc["mime_type"]
    log.info(
        "processing document %s (attempt %s/%s)", document_id, job["attempts"], job["max_attempts"]
    )

    update_processing_stage(document_id, "extracting")
    pages = extract_text(file_url, mime_type)
    store_document_text(document_id, pages)
    full_text = "\n\n".join(p["text"] for p in pages)

    update_processing_stage(document_id, "simplifying")
    insight = simplify_document(full_text)

    update_processing_stage(document_id, "embedding")
    embed_and_store(document_id, chunk_pages(pages))

    update_processing_stage(document_id, "tables")
    _store_tables(document_id, extract_tables(file_url, mime_type))

    update_processing_stage(document_id, "finalizing")
    _upsert_insight(document_id, insight)
    with cursor() as cur:
        cur.execute(
            "UPDATE documents SET status = 'ready', page_count = %s WHERE id = %s",
            (len(pages), document_id),
        )
    notify_status(document_id, "ready", "finalizing")
    complete(job["id"])
    log.info("document %s ready", document_id)


def _handle_failure(job: dict, exc: Exception) -> None:
    err = f"{type(exc).__name__}: {exc}"
    log.error("document %s failed: %s\n%s", job["document_id"], err, traceback.format_exc())
    permanent = fail(job, err)
    if permanent:
        with cursor() as cur:
            cur.execute(
                "UPDATE documents SET status = 'failed', processing_stage = 'failed' WHERE id = %s",
                (job["document_id"],),
            )
        notify_status(str(job["document_id"]), "failed", "failed")


def main() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    get_pool()
    log.info(
        "started; poll=%ss stuck-threshold=%sm",
        settings.worker_poll_interval_seconds,
        settings.worker_stuck_threshold_minutes,
    )

    last_sweep = 0.0
    while _running:
        now = time.monotonic()
        if now - last_sweep > 60:
            swept = sweep_stuck()
            if swept:
                log.warning("stuck-document sweep marked %s document(s) failed", swept)
            last_sweep = now

        job = claim_next()
        if job is None:
            time.sleep(settings.worker_poll_interval_seconds)
            continue

        try:
            process_document(job)
        except Exception as exc:  # noqa: BLE001 - queue decides retry vs. give up
            _handle_failure(job, exc)

    close_pool()
    log.info("stopped")


if __name__ == "__main__":
    main()

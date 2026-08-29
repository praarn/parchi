"""In-process fan-out of document-processing progress to WebSocket clients.

The worker runs in a *separate* container, so it can't call into this process
directly. It signals progress with Postgres ``NOTIFY parchi_progress`` (see
``db.update_processing_stage`` / ``db.notify_status``). One listener task per API
process holds a dedicated async connection, and every notification is fanned out
to the WebSockets currently watching that document.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

import psycopg
from fastapi import WebSocket

from app.config import settings

log = logging.getLogger("parchi.events")

CHANNEL = "parchi_progress"

_subscribers: dict[str, set[WebSocket]] = {}
_lock = asyncio.Lock()


async def register(document_id: str, ws: WebSocket) -> None:
    async with _lock:
        _subscribers.setdefault(document_id, set()).add(ws)


async def unregister(document_id: str, ws: WebSocket) -> None:
    async with _lock:
        conns = _subscribers.get(document_id)
        if conns:
            conns.discard(ws)
            if not conns:
                _subscribers.pop(document_id, None)


async def _fan_out(document_id: str, message: dict) -> None:
    async with _lock:
        targets = list(_subscribers.get(document_id, ()))
    for ws in targets:
        try:
            await ws.send_json(message)
        except Exception:
            await unregister(document_id, ws)


async def pg_listener(stop: asyncio.Event) -> None:
    """Long-lived: LISTEN on the progress channel and fan out. Reconnects on error.

    If this can't run (it needs psycopg async), the WebSocket endpoint's own
    safety poll still delivers progress within a few seconds — just not instantly.
    """
    warned = False
    while not stop.is_set():
        try:
            aconn = await psycopg.AsyncConnection.connect(
                settings.database_url, autocommit=True, client_encoding="UTF8"
            )
        except Exception as exc:  # pragma: no cover - infra
            if not warned:
                log.warning("progress listener unavailable (%s); WS falls back to polling", exc)
                warned = True
            await asyncio.sleep(15)
            continue
        warned = False

        try:
            await aconn.execute(f"LISTEN {CHANNEL}")
            log.info("progress listener: subscribed to %s", CHANNEL)
            # Blocks until a notification arrives. Shutdown cancels this task,
            # which unwinds cleanly through the finally below; a connection
            # error drops to the reconnect loop.
            async for notify in aconn.notifies():
                try:
                    payload = json.loads(notify.payload)
                except json.JSONDecodeError:
                    continue
                doc_id = str(payload.get("document_id", ""))
                if doc_id:
                    await _fan_out(doc_id, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - infra
            log.warning("progress listener: dropped (%s); reconnecting", exc)
            await asyncio.sleep(2)
        finally:
            with contextlib.suppress(Exception):
                await aconn.close()

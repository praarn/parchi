"""Parchi API — the single backend service.

Owns auth, documents, chat, live progress (WebSocket) and stats. Background
document processing runs in a separate worker process (``python -m app.worker``)
against the shared Postgres job queue.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# psycopg's async mode can't run on Windows' default Proactor loop, which the
# progress listener needs. Harmless no-op on Linux (Docker), where this branch
# isn't taken.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.config import settings
from app.db import close_pool, get_pool
from app.events import pg_listener
from app.routers import auth, chat, documents, ws

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_pool()  # open the pool eagerly so a bad DATABASE_URL fails at boot
    stop = asyncio.Event()
    listener = asyncio.create_task(pg_listener(stop)) if settings.enable_progress_listener else None
    try:
        yield
    finally:
        stop.set()
        if listener is not None:
            listener.cancel()
            try:
                await asyncio.wait_for(listener, timeout=5)
            except (TimeoutError, asyncio.CancelledError, Exception):
                pass
        close_pool()


app = FastAPI(title="Parchi API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(ws.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}

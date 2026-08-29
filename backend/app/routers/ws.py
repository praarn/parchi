"""WebSocket: live document-processing progress.

Client connects to ``/ws/documents/{id}?token=<access token>`` (browsers can't
set an ``Authorization`` header on a WebSocket, so the short-lived access token
rides in the query string). The socket:

1. authenticates and checks the caller owns the document,
2. sends the current ``{status, stage}`` immediately (so late joiners catch up),
3. streams every progress update pushed by the worker via Postgres NOTIFY,
4. also runs a slow safety poll, and closes itself once the document reaches a
   terminal ``ready`` / ``failed`` state.
"""

from __future__ import annotations

import asyncio

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db import query_one
from app.events import register, unregister
from app.security import decode_access_token

router = APIRouter(tags=["ws"])

TERMINAL = {"ready", "failed"}


def _document_state(document_id: str, user_id: str) -> dict | None:
    return query_one(
        "SELECT status, processing_stage FROM documents WHERE id = %s AND user_id = %s",
        (document_id, user_id),
    )


@router.websocket("/ws/documents/{document_id}")
async def document_progress(websocket: WebSocket, document_id: str, token: str = "") -> None:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=4401)
        return

    user_id = payload["sub"]
    state = await asyncio.to_thread(_document_state, document_id, user_id)
    if state is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    await register(document_id, websocket)
    try:
        await websocket.send_json(
            {
                "document_id": document_id,
                "status": state["status"],
                "stage": state["processing_stage"],
            }
        )
        if state["status"] in TERMINAL:
            return

        # Safety net in case a NOTIFY is missed: poll the row periodically and
        # bail out on a terminal status.
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
            except TimeoutError:
                pass
            except WebSocketDisconnect:
                break
            latest = await asyncio.to_thread(_document_state, document_id, user_id)
            if latest is None:
                break
            await websocket.send_json(
                {
                    "document_id": document_id,
                    "status": latest["status"],
                    "stage": latest["processing_stage"],
                }
            )
            if latest["status"] in TERMINAL:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await unregister(document_id, websocket)

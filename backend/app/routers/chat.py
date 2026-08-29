"""RAG chat over a single document."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.db import cursor, query_all, query_one
from app.deps import CurrentUser, get_current_user
from app.models import ChatAnswerResponse, ChatHistoryResponse, ChatRequest
from app.pipeline.qa import answer_question

router = APIRouter(prefix="/documents", tags=["chat"])


def _require_document(document_id: str, user_id: str) -> None:
    if not query_one(
        "SELECT 1 FROM documents WHERE id = %s AND user_id = %s", (document_id, user_id)
    ):
        raise HTTPException(status_code=404, detail="Document not found")


def _get_or_create_session(document_id: str, user_id: str) -> str:
    row = query_one(
        """
        SELECT id FROM chat_sessions
         WHERE document_id = %s AND user_id = %s
         ORDER BY created_at DESC LIMIT 1
        """,
        (document_id, user_id),
    )
    if row:
        return str(row["id"])
    created = query_one(
        "INSERT INTO chat_sessions (document_id, user_id) VALUES (%s, %s) RETURNING id",
        (document_id, user_id),
    )
    return str(created["id"])


@router.post("/{document_id}/chat", response_model=ChatAnswerResponse)
def send_message(
    document_id: str,
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ChatAnswerResponse:
    _require_document(document_id, user.id)
    session_id = _get_or_create_session(document_id, user.id)

    history = query_all(
        "SELECT role, content FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
        (session_id,),
    )
    with cursor() as cur:
        cur.execute(
            "INSERT INTO chat_messages (session_id, role, content, language) VALUES (%s, 'user', %s, %s)",
            (session_id, body.message, body.language),
        )

    result = answer_question(document_id, body.message, history, body.language)

    with cursor() as cur:
        cur.execute(
            "INSERT INTO chat_messages (session_id, role, content, language) VALUES (%s, 'assistant', %s, %s)",
            (session_id, result["answer"], body.language),
        )
    return ChatAnswerResponse(answer=result["answer"], sources=result.get("sources", []))


@router.get("/{document_id}/chat", response_model=ChatHistoryResponse)
def get_history(
    document_id: str, user: CurrentUser = Depends(get_current_user)
) -> ChatHistoryResponse:
    _require_document(document_id, user.id)
    row = query_one(
        """
        SELECT id FROM chat_sessions
         WHERE document_id = %s AND user_id = %s
         ORDER BY created_at DESC LIMIT 1
        """,
        (document_id, user.id),
    )
    if not row:
        return ChatHistoryResponse(messages=[])
    messages = query_all(
        """
        SELECT role, content, language, created_at
          FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC
        """,
        (str(row["id"]),),
    )
    return ChatHistoryResponse(messages=messages)

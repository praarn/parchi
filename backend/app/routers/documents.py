"""Documents: upload, process, list, detail, translate, tables, share, stats."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from app.config import settings
from app.db import cursor, query_all, query_one
from app.deps import CurrentUser, get_current_user
from app.models import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentOut,
    InsightOut,
    Pagination,
    ShareResponse,
    StatsResponse,
    TablesResponse,
    TranslateRequest,
    TranslateResponse,
    UploadResponse,
)
from app.pipeline.translate import translate_insight
from app.queue import enqueue

router = APIRouter(prefix="/documents", tags=["documents"])

ACCEPTED_MIME = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _doc_out(row: dict) -> DocumentOut:
    return DocumentOut(
        id=str(row["id"]),
        original_filename=row.get("original_filename"),
        mime_type=row.get("mime_type"),
        status=row["status"],
        processing_stage=row.get("processing_stage"),
        page_count=row.get("page_count"),
        created_at=row.get("created_at"),
    )


def _owned_document(document_id: str, user_id: str) -> dict:
    row = query_one(
        "SELECT * FROM documents WHERE id = %s AND user_id = %s",
        (document_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


def _insight_out(row: dict | None) -> InsightOut | None:
    if not row:
        return None
    return InsightOut(
        language=row["language"],
        summary=row["summary"],
        key_points=row["key_points"],
        deadlines=row["deadlines"],
        eligibility=row["eligibility"],
        explain_like_10=row["explain_like_10"],
    )


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
) -> UploadResponse:
    ext = ACCEPTED_MIME.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, PNG, JPEG or WebP files are accepted",
        )

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb}MB limit",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_hash = hashlib.sha256(data).hexdigest()
    existing = query_one(
        "SELECT * FROM documents WHERE file_hash = %s AND user_id = %s",
        (file_hash, user.id),
    )
    if existing:
        return UploadResponse(document=_doc_out(existing), deduped=True)

    path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    path.write_bytes(data)

    row = query_one(
        """
        INSERT INTO documents
            (user_id, file_url, file_hash, mime_type, original_filename, status)
        VALUES (%s, %s, %s, %s, %s, 'uploaded')
        RETURNING *
        """,
        (user.id, str(path), file_hash, file.content_type, file.filename),
    )
    return UploadResponse(document=_doc_out(row), deduped=False)


@router.post("/{document_id}/process")
def process(document_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    _owned_document(document_id, user.id)
    with cursor() as cur:
        cur.execute(
            """
            UPDATE documents
               SET status = 'processing', processing_stage = NULL, processing_started_at = now()
             WHERE id = %s
            """,
            (document_id,),
        )
    enqueue(document_id)
    return {"status": "processing"}


@router.get("/stats", response_model=StatsResponse)
def stats(user: CurrentUser = Depends(get_current_user)) -> StatsResponse:
    rows = query_all(
        "SELECT status, page_count, created_at FROM documents WHERE user_id = %s",
        (user.id,),
    )
    if not rows:
        return StatsResponse(total=0, by_status={}, avg_page_count=None, uploads_last_14_days=[])

    df = pd.DataFrame(rows, columns=["status", "page_count", "created_at"])

    by_status = df["status"].value_counts().to_dict()
    avg_pages = df["page_count"].dropna()
    avg = round(float(avg_pages.mean()), 1) if not avg_pages.empty else None

    df["day"] = pd.to_datetime(df["created_at"], utc=True).dt.strftime("%Y-%m-%d")
    counts = df.groupby("day").size()
    today = datetime.now(UTC).date()
    window = [(today - timedelta(days=n)).isoformat() for n in range(13, -1, -1)]
    uploads = [{"day": day, "count": int(counts.get(day, 0))} for day in window]

    return StatsResponse(
        total=int(len(df)),
        by_status={str(k): int(v) for k, v in by_status.items()},
        avg_page_count=avg,
        uploads_last_14_days=uploads,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DocumentListResponse:
    rows = query_all(
        "SELECT * FROM documents WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (user.id, limit, offset),
    )
    total = query_one(
        "SELECT COUNT(*)::int AS total FROM documents WHERE user_id = %s", (user.id,)
    )["total"]
    return DocumentListResponse(
        documents=[_doc_out(r) for r in rows],
        pagination=Pagination(limit=limit, offset=offset, total=total),
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    language: str = "en",
) -> DocumentDetailResponse:
    doc = _owned_document(document_id, user.id)
    insight = query_one(
        "SELECT * FROM document_insights WHERE document_id = %s AND language = %s",
        (document_id, language),
    )
    return DocumentDetailResponse(document=_doc_out(doc), insight=_insight_out(insight))


@router.post("/{document_id}/translate", response_model=TranslateResponse)
def translate(
    document_id: str,
    body: TranslateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> TranslateResponse:
    _owned_document(document_id, user.id)
    if body.language == "en":
        raise HTTPException(status_code=400, detail="Document is already in English")

    cached = query_one(
        "SELECT * FROM document_insights WHERE document_id = %s AND language = %s",
        (document_id, body.language),
    )
    if cached:
        return TranslateResponse(insight=_insight_out(cached), cached=True)

    english = query_one(
        "SELECT * FROM document_insights WHERE document_id = %s AND language = 'en'",
        (document_id,),
    )
    if not english:
        raise HTTPException(
            status_code=409,
            detail="Document must finish processing (English) before translation",
        )

    translated = translate_insight(
        {
            "summary": english["summary"],
            "key_points": english["key_points"],
            "deadlines": english["deadlines"],
            "eligibility": english["eligibility"],
            "explain_like_10": english["explain_like_10"],
        },
        body.language,
    )
    inserted = query_one(
        """
        INSERT INTO document_insights
            (document_id, language, summary, key_points, deadlines, eligibility, explain_like_10)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            document_id,
            body.language,
            translated.get("summary"),
            json.dumps(translated.get("key_points", [])),
            json.dumps(translated.get("deadlines", [])),
            json.dumps(translated.get("eligibility", {})),
            translated.get("explain_like_10"),
        ),
    )
    return TranslateResponse(insight=_insight_out(inserted), cached=False)


@router.get("/{document_id}/tables", response_model=TablesResponse)
def tables(document_id: str, user: CurrentUser = Depends(get_current_user)) -> TablesResponse:
    _owned_document(document_id, user.id)
    rows = query_all(
        "SELECT page_number, data FROM document_tables WHERE document_id = %s ORDER BY page_number",
        (document_id,),
    )
    return TablesResponse(
        tables=[{"page_number": r["page_number"], "data": r["data"]} for r in rows]
    )


@router.post("/{document_id}/share", response_model=ShareResponse)
def share(
    document_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    language: str = "en",
) -> ShareResponse:
    _owned_document(document_id, user.id)
    insight = query_one(
        "SELECT summary FROM document_insights WHERE document_id = %s AND language = %s",
        (document_id, language),
    )
    summary = (insight or {}).get("summary") or "Check out this document summary."
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    text = quote(f"{summary}\n\nView full details: {origin}/document/{document_id}")
    return ShareResponse(whatsapp_url=f"https://wa.me/?text={text}")

"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

# --- Auth ---------------------------------------------------------------


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = None
    preferred_language: str = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    preferred_language: str = "en"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(TokenPair):
    user: UserOut


# --- Documents --------------------------------------------------------


class DocumentOut(BaseModel):
    id: str
    original_filename: str | None = None
    mime_type: str | None = None
    status: str
    processing_stage: str | None = None
    page_count: int | None = None
    created_at: datetime | None = None


class UploadResponse(BaseModel):
    document: DocumentOut
    deduped: bool = False


class InsightOut(BaseModel):
    language: str = "en"
    summary: str | None = None
    key_points: Any = None
    deadlines: Any = None
    eligibility: Any = None
    explain_like_10: str | None = None


class DocumentDetailResponse(BaseModel):
    document: DocumentOut
    insight: InsightOut | None = None


class Pagination(BaseModel):
    limit: int
    offset: int
    total: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]
    pagination: Pagination


class TranslateRequest(BaseModel):
    language: str


class TranslateResponse(BaseModel):
    insight: InsightOut
    cached: bool = False


class TableOut(BaseModel):
    page_number: int | None = None
    data: Any = None


class TablesResponse(BaseModel):
    tables: list[TableOut]


class ShareResponse(BaseModel):
    whatsapp_url: str


class StatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    avg_page_count: float | None = None
    uploads_last_14_days: list[dict[str, Any]]


# --- Chat ------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    language: str = "en"


class ChatMessageOut(BaseModel):
    role: str
    content: str
    language: str | None = None
    created_at: datetime | None = None


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageOut]


class ChatAnswerResponse(BaseModel):
    answer: str
    sources: list[int] = []

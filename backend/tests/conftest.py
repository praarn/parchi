"""Shared test fixtures.

DB-backed tests need a reachable Postgres with the project schema (the simplest
way: ``docker compose up -d postgres``). If it's not reachable the DB fixtures
skip rather than fail, so ``pytest`` still runs the pure-logic tests anywhere.
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql://bureaucracy:bureaucracy@localhost:5432/bureaucracy"
)
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789abcdef")
os.environ.setdefault("GROQ_API_KEY", "test-dummy-key")
os.environ.setdefault("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "_uploads"))
os.environ["ENABLE_PROGRESS_LISTENER"] = "false"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402

_TABLES = [
    "chat_messages",
    "chat_sessions",
    "document_tables",
    "document_vectorizers",
    "embeddings",
    "document_text",
    "document_insights",
    "jobs",
    "documents",
    "refresh_tokens",
    "users",
]


def _db_reachable() -> bool:
    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


DB_UP = _db_reachable()
requires_db = pytest.mark.skipif(not DB_UP, reason="Postgres not reachable")


@pytest.fixture
def db():
    if not DB_UP:
        pytest.skip("Postgres not reachable")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE " + ", ".join(_TABLES) + " RESTART IDENTITY CASCADE")
        yield conn
        conn.execute("TRUNCATE " + ", ".join(_TABLES) + " RESTART IDENTITY CASCADE")


@pytest.fixture
def client(db):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client):
    """A TestClient with a signed-up user's bearer token attached."""
    resp = client.post(
        "/auth/signup",
        json={"email": "test@example.com", "password": "supersecret1", "name": "Test"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client

"""Document upload / listing / ownership / dedup / queueing."""

from __future__ import annotations

import io

import fitz  # PyMuPDF

from tests.conftest import requires_db


def _tiny_pdf(text: str = "Ration card renewal notice. Applicants must be residents.") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _upload(client, data: bytes, name="notice.pdf", mime="application/pdf"):
    return client.post(
        "/documents/upload",
        files={"file": (name, io.BytesIO(data), mime)},
    )


@requires_db
def test_upload_then_list(auth_client):
    r = _upload(auth_client, _tiny_pdf())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["deduped"] is False
    assert body["document"]["status"] == "uploaded"

    r = auth_client.get("/documents")
    assert r.status_code == 200
    listing = r.json()
    assert listing["pagination"]["total"] == 1
    assert len(listing["documents"]) == 1


@requires_db
def test_upload_is_deduplicated_by_content_hash(auth_client):
    data = _tiny_pdf()
    first = _upload(auth_client, data).json()["document"]["id"]
    second = _upload(auth_client, data).json()
    assert second["deduped"] is True
    assert second["document"]["id"] == first


@requires_db
def test_rejects_unsupported_file_type(auth_client):
    r = auth_client.post(
        "/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 415


@requires_db
def test_process_enqueues_a_job(auth_client):
    doc_id = _upload(auth_client, _tiny_pdf()).json()["document"]["id"]
    r = auth_client.post(f"/documents/{doc_id}/process")
    assert r.status_code == 200
    assert r.json()["status"] == "processing"

    from app.db import query_one

    job = query_one("SELECT * FROM jobs WHERE document_id = %s", (doc_id,))
    assert job is not None and job["status"] == "queued"
    doc = query_one("SELECT status FROM documents WHERE id = %s", (doc_id,))
    assert doc["status"] == "processing"


@requires_db
def test_other_users_document_is_not_visible(client):
    a = client.post("/auth/signup", json={"email": "a@x.com", "password": "passwordone1"}).json()[
        "access_token"
    ]
    b = client.post("/auth/signup", json={"email": "b@x.com", "password": "passwordtwo2"}).json()[
        "access_token"
    ]

    client.headers.update({"Authorization": f"Bearer {a}"})
    doc_id = _upload(client, _tiny_pdf()).json()["document"]["id"]

    client.headers.update({"Authorization": f"Bearer {b}"})
    assert client.get(f"/documents/{doc_id}").status_code == 404


@requires_db
def test_two_users_can_upload_the_same_file(client):
    """Dedup is per-user: the same public notice from two accounts must not
    collide on the file hash."""
    data = _tiny_pdf()
    a = client.post("/auth/signup", json={"email": "ua@x.com", "password": "passwordone1"}).json()[
        "access_token"
    ]
    b = client.post("/auth/signup", json={"email": "ub@x.com", "password": "passwordtwo2"}).json()[
        "access_token"
    ]

    client.headers.update({"Authorization": f"Bearer {a}"})
    r1 = _upload(client, data)
    client.headers.update({"Authorization": f"Bearer {b}"})
    r2 = _upload(client, data)

    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["deduped"] is False and r2.json()["deduped"] is False
    assert r1.json()["document"]["id"] != r2.json()["document"]["id"]


@requires_db
def test_stats_shape(auth_client):
    _upload(auth_client, _tiny_pdf())
    r = auth_client.get("/documents/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["by_status"] == {"uploaded": 1}
    assert len(body["uploads_last_14_days"]) == 14

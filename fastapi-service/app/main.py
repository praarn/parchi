from dotenv import load_dotenv
load_dotenv(encoding="utf-8-sig")  # utf-8-sig strips a BOM if present, no-op if not

import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.pipeline.extract import extract_text
from app.pipeline.chunk import chunk_pages
from app.pipeline.simplify import simplify_document
from app.pipeline.translate import translate_insight
from app.pipeline.embed import embed_and_store
from app.pipeline.qa import answer_question

app = FastAPI(title="AI Bureaucracy Simplifier — AI Service")

INTERNAL_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")


def check_internal_auth(x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal service token")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- /internal/extract ----------

class ExtractRequest(BaseModel):
    pdf_path: str


@app.post("/internal/extract")
def internal_extract(req: ExtractRequest, x_internal_token: str = Header(default="")):
    check_internal_auth(x_internal_token)
    pages = extract_text(req.pdf_path)
    return {"pages": pages, "page_count": len(pages)}


# ---------- /internal/simplify ----------

class SimplifyRequest(BaseModel):
    full_text: str


@app.post("/internal/simplify")
def internal_simplify(req: SimplifyRequest, x_internal_token: str = Header(default="")):
    check_internal_auth(x_internal_token)
    return simplify_document(req.full_text)


# ---------- /internal/translate ----------

class TranslateRequest(BaseModel):
    insight: dict
    language: str


@app.post("/internal/translate")
def internal_translate(req: TranslateRequest, x_internal_token: str = Header(default="")):
    check_internal_auth(x_internal_token)
    return translate_insight(req.insight, req.language)


# ---------- /internal/embed ----------

class EmbedRequest(BaseModel):
    document_id: str
    pages: list[dict]


@app.post("/internal/embed")
def internal_embed(req: EmbedRequest, x_internal_token: str = Header(default="")):
    check_internal_auth(x_internal_token)
    chunks = chunk_pages(req.pages)
    count = embed_and_store(req.document_id, chunks)
    return {"chunks_stored": count}


# ---------- /internal/qa ----------

class QARequest(BaseModel):
    document_id: str
    question: str
    history: list[dict] = []
    language: str = "en"


@app.post("/internal/qa")
def internal_qa(req: QARequest, x_internal_token: str = Header(default="")):
    check_internal_auth(x_internal_token)
    return answer_question(req.document_id, req.question, req.history, req.language)


# ---------- /internal/process (full pipeline, used by the Node worker) ----------

class ProcessRequest(BaseModel):
    document_id: str
    pdf_path: str


@app.post("/internal/process")
def internal_process(req: ProcessRequest, x_internal_token: str = Header(default="")):
    """Runs extraction -> simplify -> embed in one call. The Node-side BullMQ
    worker calls this single endpoint so the queue job stays simple; each
    stage below is still its own reusable function/pipeline module."""
    check_internal_auth(x_internal_token)

    pages = extract_text(req.pdf_path)
    full_text = "\n\n".join(p["text"] for p in pages)

    insight = simplify_document(full_text)
    chunks = chunk_pages(pages)
    embed_and_store(req.document_id, chunks)

    return {
        "page_count": len(pages),
        "insight": insight,
    }
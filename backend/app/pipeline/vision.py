"""Vision extraction for photographed / scanned documents.

Used by ``extract.py`` when the upload is an image (or a PDF page that has
almost no embedded text). Groq's Llama-4 Scout is natively multimodal, so we
hand it the image and ask for a faithful transcription plus a note of any
stamps/signatures/handwriting that OCR alone would miss.
"""

from __future__ import annotations

from app.llm_client import call_vision

_SYSTEM = (
    "You transcribe images of official/government documents for a downstream "
    "summariser. Be faithful and complete."
)

_PROMPT = (
    "Transcribe ALL text visible in this document image, preserving reading "
    "order and line breaks. Keep numbers, dates, form/section numbers and "
    "names exact. After the transcription, add a short line starting with "
    "'[VISUAL]' noting any stamps, seals, signatures, checkboxes, handwriting "
    "or tables you can see. Do not summarise or interpret."
)


def describe_document_image(image_path: str) -> str:
    """Return a plain-text transcription of the image. Raises on API failure so
    the caller can fall back to OCR."""
    return call_vision(_SYSTEM, _PROMPT, image_path, max_tokens=2000).strip()

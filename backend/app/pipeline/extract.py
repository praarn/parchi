"""Text extraction — the multimodal front door of the pipeline.

Accepts either a PDF or a single image (a photo of a document):

- **PDF**  -> PyMuPDF native text, page by page. A page with almost no text is
  treated as scanned and sent through OCR (Tesseract) when that tooling is
  present, otherwise left as-is.
- **Image** (png/jpg/webp) -> Groq vision transcription when a key is
  configured, with Tesseract OCR as the offline fallback. Returned as a
  single page.

Everything downstream (chunk / simplify / embed / tables) just sees a list of
``{"page_number": int, "text": str}``.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF

# OCR is optional at runtime: it needs the `tesseract-ocr` system package (+
# poppler for pdf2image). If missing we degrade instead of crashing.
try:
    import pytesseract
    from pdf2image import convert_from_path

    OCR_AVAILABLE = True
except Exception:  # pragma: no cover - depends on host packages
    OCR_AVAILABLE = False

IMAGE_MIME_PREFIXES = ("image/",)
_MIN_NATIVE_CHARS = 40


def clean_text(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw)
    text = re.sub(r"Page \d+ of \d+", "", text)
    return text.strip()


def _ocr_image_file(path: str) -> str:
    if not OCR_AVAILABLE:
        return ""
    try:
        return pytesseract.image_to_string(path, lang="eng+hin")
    except Exception as exc:  # pragma: no cover
        print(f"[extract] OCR failed on image {path}: {exc}")
        return ""


def _extract_image(path: str) -> list[dict]:
    """A photographed/scanned single-image document."""
    text = ""
    try:
        from app.pipeline.vision import describe_document_image

        text = describe_document_image(path)
    except Exception as exc:
        print(f"[extract] vision transcription unavailable ({exc}); falling back to OCR")
        text = _ocr_image_file(path)

    if len(text.strip()) < _MIN_NATIVE_CHARS:
        ocr = _ocr_image_file(path)
        if len(ocr.strip()) > len(text.strip()):
            text = ocr

    return [{"page_number": 1, "text": clean_text(text)}]


def _extract_pdf(path: str) -> list[dict]:
    doc = fitz.open(path)
    pages: list[dict] = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if len(text.strip()) < _MIN_NATIVE_CHARS and OCR_AVAILABLE:
            try:
                images = convert_from_path(path, first_page=i + 1, last_page=i + 1)
                text = pytesseract.image_to_string(images[0], lang="eng+hin")
            except Exception as exc:
                print(f"[extract] OCR failed on page {i + 1}, using native text: {exc}")
        pages.append({"page_number": i + 1, "text": clean_text(text)})
    doc.close()
    return pages


def extract_text(file_path: str, mime_type: str | None = None) -> list[dict]:
    is_image = (mime_type or "").startswith(IMAGE_MIME_PREFIXES) or file_path.lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff")
    )
    if is_image:
        return _extract_image(file_path)
    return _extract_pdf(file_path)

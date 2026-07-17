import re
import fitz  # PyMuPDF

# OCR imports are optional at runtime — scanned-PDF support requires the
# `tesseract-ocr` system package AND poppler (for pdf2image) to be installed
# and on PATH. If either is missing, we fall back to native text only
# instead of crashing the whole request.
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


def clean_text(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw)
    text = re.sub(r"Page \d+ of \d+", "", text)
    return text.strip()


def extract_text(pdf_path: str) -> list[dict]:
    """Extract text page-by-page, falling back to OCR for scanned pages
    when OCR tooling is available; otherwise uses native text as-is."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if len(text.strip()) < 40 and OCR_AVAILABLE:
            try:
                images = convert_from_path(pdf_path, first_page=i + 1, last_page=i + 1)
                text = pytesseract.image_to_string(images[0], lang="eng+hin")
            except Exception as e:
                print(f"[extract] OCR failed on page {i + 1}, using native text only: {e}")
        pages.append({"page_number": i + 1, "text": clean_text(text)})
    doc.close()
    return pages
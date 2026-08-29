"""Structured table extraction (PyMuPDF -> pandas).

Government notices carry small tables — income slabs, fee schedules, checklists.
PyMuPDF's ``page.find_tables(strategy="lines_strict")`` locates *ruled* tables
(the common case in official PDFs) with essentially no false positives on prose;
pandas then normalises each into ``{columns, rows}`` JSON the frontend renders
as a real table instead of the run-on text OCR would give.

Borderless / whitespace-aligned "tables" are deliberately not chased — the
``text`` strategy turns any dense paragraph into a mangled grid, which is worse
than showing nothing. Images are skipped (no reliable geometry); their vision
transcription already flags visible tables in its ``[VISUAL]`` line.
"""

from __future__ import annotations

import fitz  # PyMuPDF
import pandas as pd

MAX_TABLES = 25


def _clean_grid(rows: list[list]) -> list[list[str]]:
    grid = [[("" if c is None else str(c)).strip() for c in r] for r in rows if r]
    return [r for r in grid if any(r)]  # drop fully-empty spacer rows


def extract_tables(file_path: str, mime_type: str | None = None) -> list[dict]:
    if (mime_type or "").startswith("image/") or not file_path.lower().endswith(".pdf"):
        return []

    out: list[dict] = []
    doc = fitz.open(file_path)
    try:
        for page_index, page in enumerate(doc):
            try:
                found = page.find_tables(strategy="lines_strict")
            except Exception as exc:  # pragma: no cover
                print(f"[tables] find_tables failed on page {page_index + 1}: {exc}")
                continue

            for table in found.tables:
                rows = _clean_grid(table.extract())
                if len(rows) < 2:
                    continue
                header, *body = rows
                columns = [(c.strip() if c.strip() else f"col_{i}") for i, c in enumerate(header)]
                df = pd.DataFrame(body, columns=columns).fillna("")
                if df.empty or df.shape[1] < 2:
                    continue
                out.append(
                    {
                        "page_number": page_index + 1,
                        "data": {
                            "columns": list(df.columns),
                            "rows": df.astype(str).values.tolist(),
                        },
                    }
                )
                if len(out) >= MAX_TABLES:
                    return out
    finally:
        doc.close()
    return out

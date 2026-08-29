"""Regenerate the sample documents used for manual end-to-end testing.

    python samples/make_samples.py

Produces:
  samples/sample-notice.pdf   a two-page mock government scheme notice (with a table)
  samples/sample-notice.png   a single-page photo-style version for the multimodal path
"""

from __future__ import annotations

import pathlib

import fitz  # PyMuPDF

HERE = pathlib.Path(__file__).parent

PAGE_1 = """GOVERNMENT OF THE STATE
Department of Social Welfare

SUBJECT: Chief Minister's Household Electricity Subsidy Scheme, 2026

1. Introduction
The State Government has approved a monthly electricity bill subsidy for
low-income households. This notice explains who may apply, the documents
required, and the last date for submission.

2. Who can apply
   (a) The applicant must be a permanent resident of the State for at least
       three years.
   (b) Total annual household income must not exceed Rs. 2,50,000.
   (c) The household must have a sanctioned load of 2 kW or less.
   (d) Government employees (serving or retired) are not eligible.

3. Documents required
   - Aadhaar card of the applicant
   - Latest electricity bill (not older than two months)
   - Income certificate issued by the Tehsildar
   - Proof of residence (ration card or voter ID)

4. Benefit
Eligible households will receive a subsidy of 50% of the monthly bill,
subject to a maximum of Rs. 400 per month, credited directly to the
registered bank account.
"""

PAGE_2_HEAD = "5. Subsidy slabs\n\nThe subsidy rate depends on the household's monthly consumption:\n"

SLAB_TABLE = [
    ["Monthly units", "Subsidy rate", "Max per month"],
    ["0 - 100", "60%", "Rs. 300"],
    ["101 - 200", "50%", "Rs. 400"],
    ["201 - 300", "30%", "Rs. 400"],
    ["Above 300", "Not eligible", "-"],
]

PAGE_2 = """6. Important dates
   - Applications open: 1 September 2026
   - Last date for submission: 31 October 2026
   - Provisional list published: 20 November 2026

7. How to apply
Submit the completed form along with self-attested copies of the documents
at your nearest Common Service Centre (CSC) or online at the Department
portal. Incomplete applications will be rejected without notice.

For queries, call the helpline 1800-XXX-XXXX (Monday to Saturday, 10am-5pm).
"""


def _draw_ruled_table(page, rows, x0=56, y0=150, col_w=(150, 140, 150), row_h=24) -> float:
    """Draw a real ruled grid so find_tables(strategy='lines_strict') detects it."""
    xs = [x0] + [x0 + sum(col_w[: i + 1]) for i in range(len(col_w))]
    width, height = sum(col_w), row_h * len(rows)
    for xv in xs:
        page.draw_line((xv, y0), (xv, y0 + height), width=1)
    for i in range(len(rows) + 1):
        page.draw_line((x0, y0 + i * row_h), (x0 + width, y0 + i * row_h), width=1)
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            page.insert_textbox(
                fitz.Rect(xs[c] + 3, y0 + r * row_h + 6, xs[c + 1] - 3, y0 + (r + 1) * row_h),
                cell,
                fontsize=10,
                fontname="hebo" if r == 0 else "helv",
            )
    return y0 + height


def build_pdf() -> pathlib.Path:
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_textbox(
        fitz.Rect(56, 56, 540, 780), PAGE_1, fontsize=11, fontname="helv", lineheight=1.35
    )

    p2 = doc.new_page()
    p2.insert_textbox(
        fitz.Rect(56, 56, 540, 150), PAGE_2_HEAD, fontsize=11, fontname="helv", lineheight=1.35
    )
    bottom = _draw_ruled_table(p2, SLAB_TABLE)
    p2.insert_textbox(
        fitz.Rect(56, bottom + 28, 540, 780), PAGE_2, fontsize=11, fontname="helv", lineheight=1.35
    )

    out = HERE / "sample-notice.pdf"
    doc.save(out)
    doc.close()
    return out


def build_image() -> pathlib.Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(40, 40, 560, 800),
        PAGE_1,
        fontsize=12,
        fontname="helv",
        lineheight=1.4,
    )
    pix = page.get_pixmap(dpi=150)
    out = HERE / "sample-notice.png"
    pix.save(out)
    doc.close()
    return out


if __name__ == "__main__":
    print("wrote", build_pdf())
    print("wrote", build_image())

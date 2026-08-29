# backend/app/pipeline/ — the document pipeline

The worker runs these stages in order for every document:

```
extract → (chunk) → simplify → embed → tables → finalize
```

Each module is a plain function with no framework dependency, so it's unit-
testable and reusable.

| file | what it does | notes |
|------|--------------|-------|
| `extract.py` | file → `[{page_number, text}]` | **multimodal front door.** PDF: PyMuPDF native text, per-page OCR fallback for scanned pages. Image (png/jpg/webp): Groq vision transcription, with Tesseract OCR as the offline fallback. |
| `vision.py` | one image → faithful text transcription | Groq Llama-4 Scout. Asked to transcribe exactly and flag stamps/signatures/handwriting on a `[VISUAL]` line — never to summarise. |
| `chunk.py` | pages → ~500-token overlapping chunks | splits on sentence boundaries for **Latin and Devanagari** (`. ! ? । ॥`) before falling back to token windows. |
| `embed.py` | chunks → 256-d vectors in pgvector | **deterministic LSA, no embeddings API.** Per document: `TfidfVectorizer` (word 1–2 grams + char 3–5 grams) → `TruncatedSVD` → L2 normalise. The fitted transformer is pickled into `document_vectorizers` so a later question is projected into the same space. Char n-grams let "residency" match "residents" and survive transliteration wobble. |
| `simplify.py` | full text → structured insight JSON | Groq JSON mode: summary, key points, deadlines, eligibility object, "explain like I'm 10". Retries once with a stricter instruction if the model wraps the JSON in prose. |
| `qa.py` | question → grounded answer + page sources | retrieves top-k chunks via `embed.retrieve_top_chunks`, answers **only** from that context, returns which pages it used. |
| `translate.py` | English insight → same shape in another language | Groq JSON mode; results are cached per `(document, language)` by the caller. |
| `tables.py` | PDF → `[{page_number, data}]` via pandas | `find_tables(strategy="lines_strict")` only — ruled tables, ~zero false positives on prose. Borderless "tables" are deliberately not chased; the `text` strategy turns any paragraph into a mangled grid. |

## Why LSA instead of a hosted embedding model

It runs with **only** a Groq key — no embeddings account, no per-query cost, and
it's fully deterministic (reproducible retrieval, easy to test). The trade-off is
lower semantic recall than a large embedding model; the word+char TF-IDF feature
union claws back most of what pure bag-of-words loses on morphological variants.
Swapping in a real embedding model later means changing one function and the
`VECTOR(256)` dimension in `database/schema.sql`.

import re

import tiktoken

ENCODER = tiktoken.get_encoding("cl100k_base")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Sentence terminators: Latin (. ! ?) plus the Devanagari danda (।) and
# double danda (॥) used to end sentences in Hindi, Marathi, and several
# other Indic scripts this app translates into. The original version only
# split on ".", which silently turned every non-Latin-script page into one
# giant run-on "sentence" with no real chunk boundaries — this app
# explicitly targets multilingual government documents, so that was a real
# gap, not a cosmetic one.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।॥])\s+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Turn extracted pages into overlapping ~500-token chunks.

    Splits on sentence boundaries first (Latin and Devanagari terminators),
    then falls back to fixed-size token windows so we don't cut a sentence
    in half.
    """
    chunks = []
    chunk_index = 0
    for page in pages:
        sentences = _split_sentences(page["text"])
        buffer = ""
        for sentence in sentences:
            candidate = f"{buffer} {sentence}" if buffer else sentence
            if len(ENCODER.encode(candidate)) > CHUNK_SIZE and buffer:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "page_number": page["page_number"],
                        "text": buffer.strip(),
                    }
                )
                chunk_index += 1
                # carry the tail of the previous buffer forward for overlap
                overlap_tokens = ENCODER.encode(buffer)[-CHUNK_OVERLAP:]
                buffer = f"{ENCODER.decode(overlap_tokens)} {sentence}"
            else:
                buffer = candidate
        if buffer.strip():
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "page_number": page["page_number"],
                    "text": buffer.strip(),
                }
            )
            chunk_index += 1
    return chunks

import tiktoken

ENCODER = tiktoken.get_encoding("cl100k_base")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Turn extracted pages into overlapping ~500-token chunks.

    Splits on paragraph boundaries first, then falls back to fixed-size
    token windows so we don't cut a sentence in half.
    """
    chunks = []
    chunk_index = 0
    for page in pages:
        paragraphs = [p.strip() for p in page["text"].split(".") if p.strip()]
        buffer = ""
        for para in paragraphs:
            candidate = f"{buffer} {para}." if buffer else f"{para}."
            if len(ENCODER.encode(candidate)) > CHUNK_SIZE and buffer:
                chunks.append({
                    "chunk_index": chunk_index,
                    "page_number": page["page_number"],
                    "text": buffer.strip(),
                })
                chunk_index += 1
                # carry the tail of the previous buffer forward for overlap
                overlap_tokens = ENCODER.encode(buffer)[-CHUNK_OVERLAP:]
                buffer = ENCODER.decode(overlap_tokens) + f" {para}."
            else:
                buffer = candidate
        if buffer.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "page_number": page["page_number"],
                "text": buffer.strip(),
            })
            chunk_index += 1
    return chunks
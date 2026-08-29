"""Retrieval embeddings — deterministic LSA, no embeddings API.

Per document we fit a small scikit-learn pipeline on that document's own chunks:

    TfidfVectorizer  ->  TruncatedSVD (LSA)  ->  L2 normalise

That gives every chunk a dense 256-d vector capturing term co-occurrence
(so "who is eligible" can match a chunk that says "applicants must be…"),
far better than the old SHA-hashed bag-of-words and still with zero API cost or
account. The fitted (vectorizer, svd) pair is pickled into
``document_vectorizers`` so a later question is projected into the *same* space.

Very short documents (< 3 chunks) can't support SVD; those fall back to a
stateless :class:`HashingVectorizer`. Vectors are always padded to 256 so they
fit the ``VECTOR(256)`` column.
"""

from __future__ import annotations

import pickle

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import Normalizer

from app.db import cursor, get_pool

DIM = 256
_MIN_DOCS_FOR_SVD = 3


def _word_char_features() -> FeatureUnion:
    """Word 1-2 grams for topical signal, plus char 3-5 grams so morphological
    variants ("residents" vs "residency") and transliteration wobble still
    match — this corpus is multilingual government prose."""
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    max_df=0.95,
                    sublinear_tf=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    lowercase=True,
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def _pad(vec: np.ndarray) -> list[float]:
    out = np.zeros(DIM, dtype=np.float32)
    n = min(DIM, vec.shape[0])
    out[:n] = vec[:n]
    return out.tolist()


def _build_transformer(texts: list[str]) -> tuple[object, int]:
    """Fit a transformer on the document's chunk texts. Returns (transformer, n_components)."""
    non_empty = [t for t in texts if t and t.strip()]
    if len(non_empty) >= _MIN_DOCS_FOR_SVD:
        features = _word_char_features()
        matrix = features.fit_transform(non_empty)
        n_components = int(min(DIM, matrix.shape[1] - 1, len(non_empty) - 1))
        n_components = max(1, n_components)
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        pipe = Pipeline([("features", features), ("svd", svd), ("norm", Normalizer(copy=False))])
        pipe.fit(non_empty)
        return pipe, n_components

    hashing = HashingVectorizer(
        n_features=DIM, alternate_sign=False, norm="l2", analyzer="char_wb", ngram_range=(3, 5)
    )
    return hashing, DIM


def _transform(transformer: object, text: str) -> list[float]:
    vec = transformer.transform([text])
    arr = np.asarray(vec.todense()).ravel() if hasattr(vec, "todense") else np.asarray(vec).ravel()
    norm = np.linalg.norm(arr) or 1.0
    return _pad(arr / norm)


def _save_transformer(document_id: str, transformer: object, n_components: int) -> None:
    payload = pickle.dumps(transformer, protocol=pickle.HIGHEST_PROTOCOL)
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_vectorizers (document_id, payload, n_components)
            VALUES (%s, %s, %s)
            ON CONFLICT (document_id)
            DO UPDATE SET payload = EXCLUDED.payload,
                          n_components = EXCLUDED.n_components,
                          created_at = now()
            """,
            (document_id, payload, n_components),
        )


def _load_transformer(document_id: str):
    with cursor() as cur:
        cur.execute(
            "SELECT payload FROM document_vectorizers WHERE document_id = %s",
            (document_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return pickle.loads(row["payload"])


def embed_and_store(document_id: str, chunks: list[dict]) -> int:
    if not chunks:
        return 0
    texts = [c["text"] for c in chunks]
    transformer, n_components = _build_transformer(texts)
    _save_transformer(document_id, transformer, n_components)

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM embeddings WHERE document_id = %s", (document_id,))
            for chunk in chunks:
                vector = _transform(transformer, chunk["text"])
                cur.execute(
                    """
                    INSERT INTO embeddings
                        (document_id, chunk_index, page_number, text, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        document_id,
                        chunk["chunk_index"],
                        chunk["page_number"],
                        chunk["text"],
                        vector,
                    ),
                )
    return len(chunks)


def retrieve_top_chunks(document_id: str, question: str, top_k: int = 5) -> list[dict]:
    transformer = _load_transformer(document_id)
    if transformer is None:
        # No fitted space (e.g. a document embedded before this pipeline existed).
        # Degrade to a keyword scan rather than returning nothing.
        with cursor() as cur:
            cur.execute(
                """
                SELECT page_number, text FROM embeddings
                 WHERE document_id = %s AND text ILIKE %s
                 ORDER BY chunk_index LIMIT %s
                """,
                (document_id, f"%{question[:60]}%", top_k),
            )
            rows = cur.fetchall()
        return [{"page_number": r["page_number"], "text": r["text"]} for r in rows]

    q_vector = _transform(transformer, question)
    with cursor() as cur:
        cur.execute(
            """
            SELECT page_number, text
              FROM embeddings
             WHERE document_id = %s
             ORDER BY embedding <=> %s::vector
             LIMIT %s
            """,
            (document_id, q_vector, top_k),
        )
        rows = cur.fetchall()
    return [{"page_number": r["page_number"], "text": r["text"]} for r in rows]

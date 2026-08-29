"""Pure-logic pipeline tests — no database, no network."""

from __future__ import annotations

import numpy as np

from app.pipeline.chunk import chunk_pages
from app.pipeline.embed import _build_transformer, _transform


def test_chunk_pages_splits_latin_and_devanagari_sentences():
    pages = [
        {
            "page_number": 1,
            "text": "This is the first sentence. यह दूसरा वाक्य है। And a third one here.",
        }
    ]
    chunks = chunk_pages(pages)
    assert chunks
    assert all(c["page_number"] == 1 for c in chunks)
    assert all(c["text"].strip() for c in chunks)
    joined = " ".join(c["text"] for c in chunks)
    assert "दूसरा" in joined


def test_chunk_pages_indexes_are_sequential():
    pages = [{"page_number": p, "text": "Sentence one. Sentence two. " * 40} for p in (1, 2)]
    chunks = chunk_pages(pages)
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_lsa_embedding_retrieves_the_relevant_chunk():
    corpus = [
        "Applicants must be residents of the state for at least three years.",
        "The office is open Monday to Friday from 10am to 5pm.",
        "Bring two passport photographs and a copy of your ration card.",
        "Late submissions attract a penalty of five hundred rupees.",
        "Widows and senior citizens are exempt from the application fee.",
    ]
    transformer, n_components = _build_transformer(corpus)
    assert 1 <= n_components <= 256

    vectors = np.array([_transform(transformer, text) for text in corpus])

    cases = {
        "how many years must applicants be residents of the state": 0,
        "what are the office opening hours": 1,
        "which documents and photographs should I bring": 2,
        "is there a penalty for submitting late": 3,
    }
    for question, expected in cases.items():
        scores = vectors @ np.array(_transform(transformer, question))
        assert int(scores.argmax()) == expected, (question, scores.round(2).tolist())


def test_transform_always_returns_256_dims():
    transformer, _ = _build_transformer(["only one short chunk of text"])
    vec = _transform(transformer, "a question")
    assert len(vec) == 256

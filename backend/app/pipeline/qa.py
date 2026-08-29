from app.llm_client import call_text
from app.pipeline.embed import retrieve_top_chunks

SYSTEM_PROMPT = """Answer only using the provided document context below.
If the answer isn't in the context, say clearly that it isn't specified in this
document — never guess or use outside knowledge, this is for legal/eligibility
questions where accuracy matters. Keep answers short and simple, in {language}."""


def answer_question(
    document_id: str, question: str, history: list[dict], language: str = "en"
) -> dict:
    chunks = retrieve_top_chunks(document_id, question, top_k=5)
    context = "\n\n".join(f"[page {c['page_number']}] {c['text']}" for c in chunks)

    messages = []
    for turn in history[-6:]:  # last 3 exchanges for context
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append(
        {
            "role": "user",
            "content": f"Document context:\n{context}\n\nQuestion: {question}",
        }
    )

    system = SYSTEM_PROMPT.format(language=language)
    answer = call_text(system, messages, max_tokens=800)
    return {"answer": answer, "sources": [c["page_number"] for c in chunks]}

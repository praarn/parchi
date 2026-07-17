from app.llm_client import call_json

SYSTEM_PROMPT = """You are simplifying a document for a citizen with limited English
proficiency and no legal background. The document may or may not be a government
scheme/eligibility notice — it could also be a general notice, report, or other text.

Return ONLY valid JSON (no markdown fences, no preamble) with exactly this shape:
{
  "summary": "2-3 sentence plain-language summary of what this document actually is and covers — this field must never be empty",
  "key_points": ["...", "..."],
  "deadlines": [{"description": "...", "date": "YYYY-MM-DD or null"}],
  "explain_like_10": "one short paragraph, extremely simple, explaining the document to a 10-year-old",
  "eligibility": {
    "who_can_apply": ["..."],
    "required_documents": ["..."],
    "conditions": ["..."],
    "exclusions": ["..."]
  }
}

The "summary", "key_points", and "explain_like_10" fields must always be filled in
based on the document's actual content, no matter what kind of document it is.
Only the "eligibility" object and "deadlines" array should be left empty
(as [] or empty lists inside eligibility) if the document genuinely has no
eligibility criteria or deadlines — never leave "summary" blank."""


def simplify_document(full_text: str) -> dict:
    if not full_text.strip():
        raise ValueError("Extracted document text is empty — nothing to summarize")

    user = f"Document:\n{full_text[:60000]}"
    result = call_json(SYSTEM_PROMPT, user, max_tokens=2000)

    if not result.get("summary", "").strip():
        print(f"[simplify] WARNING: model returned empty summary. Raw result: {result}")

    return result
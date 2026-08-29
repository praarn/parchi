import json

from app.llm_client import call_json

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "kn": "Kannada",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "bn": "Bengali",
}

SYSTEM_PROMPT = """Translate the given plain-language government-document explanation
into {language}. Preserve meaning and tone rather than translating word-for-word.
Use vocabulary a person with an 8th-grade education would understand.
Keep official terms (scheme names, form numbers) in their original form, with a short
in-language clarification in brackets if needed.

Return ONLY valid JSON with exactly this shape (same fields as the input, translated):
{{
  "summary": "...",
  "key_points": ["..."],
  "deadlines": [{{"description": "...", "date": "YYYY-MM-DD or null"}}],
  "explain_like_10": "...",
  "eligibility": {{
    "who_can_apply": ["..."],
    "required_documents": ["..."],
    "conditions": ["..."],
    "exclusions": ["..."]
  }}
}}"""


def translate_insight(insight: dict, language_code: str) -> dict:
    language = LANGUAGE_NAMES.get(language_code, language_code)
    system = SYSTEM_PROMPT.format(language=language)
    user = f"English content to translate:\n{json.dumps(insight)}"
    return call_json(system, user, max_tokens=2000)

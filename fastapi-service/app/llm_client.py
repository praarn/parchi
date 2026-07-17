import os
import json
from groq import Groq

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to fastapi-service/.env "
                "(get a free key at https://console.groq.com/keys)"
            )
        _client = Groq(api_key=api_key)
    return _client


# Strong general-purpose model on Groq's free tier. If you hit rate limits,
# llama-3.1-8b-instant is faster/cheaper with a much higher daily cap.
MODEL = "openai/gpt-oss-120b"


def _extract_json(text: str) -> dict:
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def call_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Call the model and parse a JSON object out of the response.

    Uses Groq's JSON mode when available, and retries once with a stricter
    instruction if the model still wraps the output in prose/fences —
    open-weight models follow "return only JSON" less reliably than Claude.
    """
    client = get_client()

    for attempt in range(2):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = response.choices[0].message.content
        try:
            return _extract_json(text)
        except json.JSONDecodeError:
            if attempt == 0:
                user = f"{user}\n\nReturn ONLY the JSON object. No prose, no markdown fences."
                continue
            raise


def call_text(system: str, messages: list[dict], max_tokens: int = 800) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, *messages],
    )
    return response.choices[0].message.content

def call_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Call the model and parse a JSON object out of the response.

    Uses Groq's JSON mode when available, and retries once with a stricter
    instruction if the model still wraps the output in prose/fences —
    open-weight models follow "return only JSON" less reliably than Claude.
    """
    client = get_client()

    for attempt in range(2):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = response.choices[0].message.content
        print(f"[llm_client] raw model output (attempt {attempt + 1}): {text[:500]}")
        try:
            return _extract_json(text)
        except json.JSONDecodeError:
            if attempt == 0:
                user = f"{user}\n\nReturn ONLY the JSON object. No prose, no markdown fences."
                continue
            raise
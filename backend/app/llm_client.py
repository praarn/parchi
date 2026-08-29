"""Thin wrapper around Groq chat completions.

Three entry points:
- ``call_json`` — structured output (summary, translation). Uses Groq JSON mode
  and retries once with a stricter instruction if the model still wraps the
  output in prose/fences.
- ``call_text`` — free-form answer (RAG chat).
- ``call_vision`` — multimodal: text + one image, for transcribing a photographed
  document.
"""

from __future__ import annotations

import base64
import json
import mimetypes

from groq import Groq

from app.config import settings

_client: Groq | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to fastapi-service/.env "
                "(free key at https://console.groq.com/keys)."
            )
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _extract_json(text: str) -> dict:
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def call_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    client = get_client()
    for attempt in range(2):
        response = client.chat.completions.create(
            model=settings.groq_text_model,
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
        model=settings.groq_text_model,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, *messages],
    )
    return response.choices[0].message.content


def call_vision(system: str, prompt: str, image_path: str, max_tokens: int = 1500) -> str:
    """Send one image plus a text prompt to the Groq vision model."""
    client = get_client()
    mime = mimetypes.guess_type(image_path)[0] or "image/png"
    with open(image_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    response = client.chat.completions.create(
        model=settings.groq_vision_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            },
        ],
    )
    return response.choices[0].message.content

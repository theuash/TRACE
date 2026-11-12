"""Single OpenAI-compatible entry point. Ollama, Groq and Gemini differ only by .env."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from shared.config import get_settings

MAX_PROMPT_CHARS = 6000


def make_client(timeout: float | None = None) -> OpenAI:
    settings = get_settings()
    base_url, api_key = settings.llm_base_url_and_key()
    return OpenAI(
        base_url=base_url,
        api_key=api_key or "none",
        timeout=timeout or settings.llm_timeout_s,
        max_retries=0,
    )


def complete_text(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    json_mode: bool = False,
    max_tokens: int = 300,
    timeout: float | None = None,
) -> str:
    settings = get_settings()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt[:MAX_PROMPT_CHARS]})
    kwargs: dict[str, Any] = {
        "model": model or settings.llm_model_extract,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = make_client(timeout).chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def extract_json_object(text: str) -> dict[str, Any]:
    """Some providers ignore response_format or wrap the object in prose / code fences."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object in model output: {text[:120]!r}")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
    return data


def complete_json(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = 300,
    timeout: float | None = None,
) -> dict[str, Any]:
    text = complete_text(
        prompt,
        system=system,
        model=model,
        json_mode=True,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return extract_json_object(text)

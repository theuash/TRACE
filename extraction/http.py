"""One HTTP client for SEC EDGAR: contact header, polite throttle, cache-first reads."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from shared.config import get_settings

MIN_GAP_S = 0.2  # never hammer the SEC, even if the settings say 8/s
_last_call = 0.0
_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers={"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"},
        )
    return _client


def _throttle() -> None:
    global _last_call
    gap = max(MIN_GAP_S, 1.0 / max(get_settings().sec_max_rps, 1.0))
    wait = _last_call + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def fetch(url: str, cache_path: Path) -> bytes:
    """Cache-first GET. The only function in extraction/ that talks to sec.gov."""
    if cache_path.exists():
        return cache_path.read_bytes()
    get_settings().assert_sec_user_agent()
    _throttle()
    response = get_client().get(url)
    if response.status_code == 403:
        raise RuntimeError(
            "SEC returned 403 for this User-Agent. Set SEC_USER_AGENT in .env to "
            "'Your Name your.email@example.com' and retry."
        )
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)
    return response.content


def fetch_text(url: str, cache_path: Path) -> str:
    return fetch(url, cache_path).decode("utf-8", errors="replace")


def fetch_json(url: str, cache_path: Path) -> Any:
    return json.loads(fetch_text(url, cache_path))


def reset_client() -> None:
    """Tests use this to drop a stale connection."""
    global _client
    if _client is not None:
        _client.close()
    _client = None

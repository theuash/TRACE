"""Small, cache-first SEC client for XBRL Company Facts.

Verification only: this module is never imported by extraction. Every request carries
`SEC_USER_AGENT`, the client is throttled well below SEC's 10 req/s, and a payload already on
disk means zero network calls (the pipeline must work offline).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from shared.config import get_settings

_MIN_INTERVAL_S = 0.15  # ~6.6 req/s, comfortably under SEC's ceiling
_last_request_at = 0.0


class XbrlUnavailable(RuntimeError):
    """Raised when Company Facts cannot be fetched (offline, unknown CIK, SEC error)."""


def _throttle() -> None:
    global _last_request_at
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def cache_path(cik: str) -> Path:
    settings = get_settings()
    return settings.xbrl_dir / f"CIK{cik.zfill(10)}.json"


def fetch_company_facts(cik: str, *, refresh: bool = False) -> dict[str, Any]:
    """Company Facts for one CIK. Disk cache first, then data.sec.gov."""
    settings = get_settings()
    path = cache_path(cik)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    settings.assert_sec_user_agent()
    settings.ensure_dirs()
    url = f"{settings.sec_data_url}/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    _throttle()
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:  # network failure is a normal verification outcome
        if path.exists():  # stale cache beats no answer
            return json.loads(path.read_text(encoding="utf-8"))
        raise XbrlUnavailable(f"Company Facts unavailable for CIK {cik}: {exc}") from exc

    payload = response.json()
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload

"""The SEC's own company directory: any ticker, any CIK, not only the five configured.

`https://www.sec.gov/files/company_tickers.json` is the list EDGAR's own search box uses. It is
fetched once through `extraction.http` (contact header, polite throttle, cache on disk) and
refreshed daily, so a reviewer can audit a company the demo does not ship with.
"""

from __future__ import annotations

import time
from typing import Any

from extraction import http
from shared.config import COMPANIES, get_settings
from shared.schemas import Company

DIRECTORY_URL = "https://www.sec.gov/files/company_tickers.json"
REFRESH_S = 24 * 60 * 60

_FALLBACK: list[Company] | None = None


def _path():
    return get_settings().data_dir / "edgar" / "company_tickers.json"


def parse_directory(raw: dict[str, Any]) -> list[Company]:
    """`{"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}` -> Companies.

    Rows the SEC formats differently are skipped, not fatal: the file is 10k rows of third-party
    text and one odd entry must not hide the other 9,999 companies.
    """
    out: list[Company] = []
    for entry in raw.values():
        try:
            out.append(
                Company(
                    ticker=str(entry["ticker"]).strip().upper(),
                    name=str(entry["title"]).strip(),
                    cik=f"{int(entry['cik_str']):010d}",
                )
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return out


def companies(*, refresh: bool = False) -> list[Company]:
    """Every company the SEC knows, cached. A failed refresh keeps the copy already on disk."""
    global _FALLBACK
    path = _path()
    if path.exists():
        stale = (time.time() - path.stat().st_mtime) > REFRESH_S
        if refresh or stale:
            keep = path.read_bytes()
            path.unlink()
            try:
                http.fetch(DIRECTORY_URL, path)
            except Exception:  # noqa: BLE001 - offline is normal on a demo laptop
                path.write_bytes(keep)
    if _FALLBACK is None or refresh:
        _FALLBACK = parse_directory(http.fetch_json(DIRECTORY_URL, path))
    return _FALLBACK


def reset_cache() -> None:
    """Tests and the settings page pick up a fresh directory with this."""
    global _FALLBACK
    _FALLBACK = None


def _cik(value: str) -> str | None:
    """`"320193"` and `"0000320193"` are the same CIK."""
    text = value.strip()
    return text.zfill(10) if text.isdigit() and len(text) <= 10 else None


def _rank(company: Company, query: str) -> int | None:
    """Lower is better: exact ticker, ticker prefix, name prefix, name substring."""
    ticker, name = company.ticker.upper(), company.name.upper()
    if ticker == query:
        return 0
    if ticker.startswith(query):
        return 1
    if name.startswith(query):
        return 2
    return 3 if query in name else None


def search(query: str, *, limit: int = 8, directory: list[Company] | None = None) -> list[Company]:
    """Type-ahead over tickers and names. The configured five always come first."""
    q = (query or "").strip().upper()
    if not q:
        return []
    configured = {c.ticker for c in COMPANIES}
    pool = COMPANIES + list(directory if directory is not None else companies())
    scored: list[tuple[int, int, Company]] = []
    seen: set[str] = set()
    for company in pool:
        if company.ticker in seen:
            continue
        rank = _rank(company, q)
        if rank is None:
            continue
        seen.add(company.ticker)
        scored.append((rank, 0 if company.ticker in configured else 1, company))
    # Among equals prefer common stock (no "-P" class suffix) and the shorter, plainer ticker.
    scored.sort(
        key=lambda row: (row[0], row[1], "-" in row[2].ticker, len(row[2].ticker), row[2].ticker)
    )
    return [company for _, _, company in scored[:limit]]


def resolve(value: str, *, directory: list[Company] | None = None) -> Company | None:
    """A ticker or a CIK for any company the SEC lists.

    The configured five come back without touching the network, so the demo works offline.
    """
    raw = (value or "").strip()
    if not raw:
        return None
    upper, cik = raw.upper(), _cik(raw)
    for company in COMPANIES:
        if company.ticker == upper or (cik is not None and company.cik == cik):
            return company
    pool = directory if directory is not None else companies()
    for company in pool:
        if company.ticker == upper:
            return company
    if cik is not None:
        for company in pool:
            if company.cik == cik:
                return company
    return None

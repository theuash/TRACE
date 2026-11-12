"""CIK -> latest 10-K primary document on disk. Cache-first, and never parses the filing."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from extraction import http
from shared.config import get_settings
from shared.schemas import Company, FilingRef

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


def fiscal_year(period_end: date) -> int:
    """Apple/MSFT/AMZN/TSLA label the year the period ends in; NVDA's January year-end does too."""
    return period_end.year


def newest_10k(submissions: dict[str, Any]) -> dict[str, str]:
    recent = submissions["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            return {key: recent[key][i] for key in recent}
    raise RuntimeError("No 10-K filing found in this company's submissions feed.")


def _ref_cache(ticker: str) -> Path:
    return get_settings().filings_dir / f"{ticker}_filingref.json"


def _read_cached_ref(cache: Path) -> FilingRef | None:
    if not cache.exists():
        return None
    ref = FilingRef.model_validate_json(cache.read_text(encoding="utf-8"))
    if ref.local_path and Path(ref.local_path).exists():
        return ref
    return None


def filing_ref(company: Company) -> FilingRef:
    """Return FilingRef with the HTML already on disk. Repeat calls make no network request."""
    settings = get_settings()
    settings.ensure_dirs()
    cache = _ref_cache(company.ticker)
    cached = _read_cached_ref(cache)
    if cached is not None:
        return cached

    submissions = http.fetch_json(
        SUBMISSIONS_URL.format(cik=company.cik),
        settings.data_dir / "edgar" / f"submissions_{company.cik}.json",
    )
    row = newest_10k(submissions)
    accession = row["accessionNumber"]
    document = row["primaryDocument"]
    url = ARCHIVE_URL.format(cik=company.cik, acc=accession.replace("-", ""), doc=document)
    local_path = settings.filings_dir / f"{company.ticker}_{accession}.htm"
    http.fetch(url, local_path)

    period_end = date.fromisoformat(row["reportDate"])
    ref = FilingRef(
        company=company,
        accession_number=accession,
        filing_date=date.fromisoformat(row["filingDate"]),
        fiscal_year=fiscal_year(period_end),
        period_end=period_end,
        primary_document=document,
        url=url,
        local_path=str(local_path),
    )
    cache.write_text(ref.model_dump_json(), encoding="utf-8")
    return ref

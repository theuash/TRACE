"""Shared test helpers: repo root on sys.path, plus small factories for the frozen schemas."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.schemas import Company, FilingRef  # noqa: E402


@pytest.fixture
def html_file(tmp_path):
    def _write(body: str, name: str = "filing.htm") -> Path:
        path = tmp_path / name
        path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
        return path

    return _write


@pytest.fixture
def company() -> Company:
    return Company(ticker="AAPL", name="Apple Inc.", cik="0000320193")


@pytest.fixture
def make_filing(company):
    def _make(
        ticker: str = "AAPL",
        fiscal_year: int = 2026,
        period_end: date = date(2026, 9, 27),
        local_path: str | None = None,
    ) -> FilingRef:
        return FilingRef(
            company=Company(ticker=ticker, name=f"{ticker} Inc.", cik="0000320193"),
            accession_number="0000320193-26-000026",
            filing_date=date(2026, 11, 3),
            fiscal_year=fiscal_year,
            period_end=period_end,
            primary_document="aapl-20260926.htm",
            url="https://www.sec.gov/Archives/edgar/data/320193/000032019326000026/aapl.htm",
            local_path=local_path,
        )

    return _make

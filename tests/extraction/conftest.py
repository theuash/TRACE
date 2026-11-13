"""Fixtures for the extraction tests.

These were lost during the move to PostgreSQL; they are file-based (HTML on disk) and have
nothing to do with the database, so they live here instead of in the root conftest.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from shared.config import get_company
from shared.schemas import Company, FilingRef


@pytest.fixture
def html_file(tmp_path):
    """Write a snippet of HTML to a temp file and return its path (the parser reads paths)."""

    def write(html: str) -> Path:
        path = tmp_path / "snippet.html"
        path.write_text(html, encoding="utf-8")
        return path

    return write


@pytest.fixture
def make_filing(tmp_path):
    """Return a factory that builds a FilingRef for the demo company (AAPL)."""

    def factory(**kwargs):
        company = get_company("AAPL")
        ref = FilingRef(
            company=company,
            accession_number="0000320193-26-000026",
            filing_date=date(2026, 9, 28),
            fiscal_year=2026,
            period_end=date(2026, 9, 27),
            primary_document="aapl-20260926.htm",
            url="https://www.sec.gov/Archives/edgar/data/320193/000032019326000026/aapl-20260926.htm",
            local_path=str(tmp_path / "AAPL_0000320193-26-000026.htm"),
        )
        for key, value in kwargs.items():
            setattr(ref, key, value)
        return ref

    return factory

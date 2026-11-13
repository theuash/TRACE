"""Tag selection and row construction against a synthetic Company Facts payload."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from shared.schemas import (
    Company,
    ExtractedMetric,
    Extractor,
    FilingRef,
    Metric,
    SourceEvidence,
)
from verification import ground_truth


def _filing() -> FilingRef:
    return FilingRef(
        company=Company(ticker="ACME", name="Acme", cik="0000123456"),
        accession_number="0000123456-25-000001",
        filing_date=date(2025, 2, 1),
        fiscal_year=2024,
        period_end=date(2024, 12, 31),
        primary_document="acme-20241231.htm",
        url="https://example.test/acme",
    )


def _metric(value: str, metric: Metric = Metric.REVENUE) -> ExtractedMetric:
    return ExtractedMetric(
        ticker="ACME",
        metric=metric,
        fiscal_year=2024,
        period_end=date(2024, 12, 31),
        value=Decimal(value),
        raw_text=value,
        extractor=Extractor.TABLE,
        confidence=0.9,
        evidence=SourceEvidence(snippet="s", matched_text=value, location="loc"),
    )


def _tag(tag: str, value: int, end: str = "2024-12-31") -> dict:
    return {tag: {"units": {"USD": [{"end": end, "val": value, "form": "10-K", "fy": 2024}]}}}


def test_revenue_prefers_the_specific_tag():
    payload = {"facts": {"us-gaap": {**_tag("Revenues", 1), **_tag(
        "RevenueFromContractWithCustomerExcludingAssessedTax", 2
    )}}}
    picked = ground_truth._pick(payload, Metric.REVENUE, _filing())
    assert picked == ("RevenueFromContractWithCustomerExcludingAssessedTax", Decimal(2))


def test_wrong_value_is_not_correct(monkeypatch):
    monkeypatch.setattr(
        ground_truth.xbrl_client,
        "fetch_company_facts",
        lambda cik: {"facts": {"us-gaap": _tag("Revenues", 100)}},
    )
    rows = ground_truth.verify_company(_filing(), [_metric("90")], ["ACME:revenue:2024"], [])
    assert rows[0].truth_value == Decimal(100)
    assert rows[0].extraction_correct is False
    assert rows[0].escalation_justified is True  # escalated and wrong


def test_missing_answer_key_is_recorded_not_scored(monkeypatch):
    def boom(cik):
        raise ground_truth.xbrl_client.XbrlUnavailable("offline")

    monkeypatch.setattr(ground_truth.xbrl_client, "fetch_company_facts", boom)
    rows = ground_truth.verify_company(_filing(), [_metric("100")], [], [])
    assert rows[0].truth_value is None
    assert rows[0].extraction_correct is None
    assert "no XBRL fact" in (rows[0].note or "")

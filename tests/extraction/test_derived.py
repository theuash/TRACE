from datetime import date
from decimal import Decimal

from extraction.confidence import score_metric
from extraction.pipeline import _derive_total_liabilities
from shared.schemas import ExtractedMetric, Extractor, Metric, SourceEvidence


def make(metric: Metric, value: str) -> ExtractedMetric:
    return ExtractedMetric(
        ticker="AMZN",
        metric=metric,
        fiscal_year=2026,
        period_end=date(2026, 12, 31),
        value=Decimal(value),
        raw_text=value,
        extractor=Extractor.TABLE,
        confidence=1.0,
        confidence_signals={
            "label_match": 1.0,
            "table_type": 1.0,
            "unit_clarity": 1.0,
            "period_clarity": 1.0,
            "numeric_wellformed": 1.0,
            "extractor_agreement": 1.0,
        },
        evidence=SourceEvidence(snippet="row", matched_text=value, location="balance sheet"),
    )


def test_amazon_gap_is_derived_and_capped():
    assets = make(Metric.TOTAL_ASSETS, "624894000000")
    equity = make(Metric.SHAREHOLDERS_EQUITY, "201875000000")
    derived = _derive_total_liabilities([assets, equity], {})

    assert derived is not None
    assert derived.value == Decimal("423019000000")
    assert derived.extractor is Extractor.DERIVED
    assert "derived" in derived.raw_text
    assert score_metric(derived).confidence <= 0.8


def test_nothing_derived_when_the_row_exists():
    assets = make(Metric.TOTAL_ASSETS, "624894000000")
    equity = make(Metric.SHAREHOLDERS_EQUITY, "201875000000")
    liabilities = make(Metric.TOTAL_LIABILITIES, "423019000000")
    assert _derive_total_liabilities([assets, equity, liabilities], {}) is None

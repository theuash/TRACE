from datetime import date
from decimal import Decimal

from extraction.confidence import score_metric
from shared.schemas import ExtractedMetric, Extractor, Metric, SourceEvidence

FULL = {
    "label_match": 1.0,
    "table_type": 1.0,
    "unit_clarity": 1.0,
    "period_clarity": 1.0,
    "numeric_wellformed": 1.0,
    "extractor_agreement": 1.0,
}


def make_metric(**overrides) -> ExtractedMetric:
    data = {
        "ticker": "AAPL",
        "metric": Metric.TOTAL_ASSETS,
        "fiscal_year": 2026,
        "period_end": date(2026, 9, 27),
        "value": Decimal("404548000000"),
        "raw_text": "404,548",
        "extractor": Extractor.TABLE,
        "confidence": 1.0,
        "confidence_signals": dict(FULL),
        "evidence": SourceEvidence(
            snippet="Total assets | 404,548 | 359,241",
            matched_text="404,548",
            location="balance sheet, row 'Total assets'",
        ),
    }
    data.update(overrides)
    return ExtractedMetric(**data)


def test_clean_row_is_one():
    assert score_metric(make_metric()).confidence == 1.0


def test_scoring_twice_is_identical():
    once = score_metric(make_metric())
    twice = score_metric(once)
    assert once.confidence == twice.confidence
    assert once.confidence_signals == twice.confidence_signals


def test_derived_value_is_capped_below_green():
    metric = make_metric(extractor=Extractor.DERIVED)
    assert score_metric(metric).confidence == 0.8


def test_disagreement_is_capped():
    metric = make_metric(confidence_signals={**FULL, "extractor_agreement": 0.3})
    assert score_metric(metric).confidence == 0.7


def test_missing_scale_lowers_the_score():
    metric = make_metric(confidence_signals={**FULL, "unit_clarity": 0.3})
    assert score_metric(metric).confidence < 0.9


def test_value_must_appear_in_the_evidence():
    metric = make_metric(
        evidence=SourceEvidence(snippet="some other row", matched_text="999", location="notes")
    )
    assert score_metric(metric).confidence < 1.0

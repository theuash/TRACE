"""Accuracy math: totals, escalation precision and calibration buckets."""

from __future__ import annotations

from decimal import Decimal

from shared.schemas import AccuracyRow, Metric
from verification.report import build_report


def _row(
    metric: Metric,
    *,
    truth: float | None,
    extracted: float,
    confidence: float,
    escalated: bool = False,
    justified: bool | None = None,
    note: str | None = None,
) -> AccuracyRow:
    return AccuracyRow(
        metric_id=f"TEST:{metric.value}:2025",
        ticker="TEST",
        metric=metric,
        fiscal_year=2025,
        extracted_value=Decimal(str(extracted)),
        final_value=Decimal(str(extracted)),
        truth_value=None if truth is None else Decimal(str(truth)),
        xbrl_tag=None if truth is None else "Test",
        extraction_correct=None if truth is None else extracted == truth,
        final_correct=None if truth is None else extracted == truth,
        confidence=confidence,
        escalated=escalated,
        escalation_justified=justified,
        note=note,
    )


def test_report_counts_and_missing_truth():
    rows = [
        _row(Metric.REVENUE, truth=100.0, extracted=100.0, confidence=0.9),
        _row(Metric.NET_INCOME, truth=10.0, extracted=11.0, confidence=0.7),
        _row(Metric.TOTAL_ASSETS, truth=None, extracted=5.0, confidence=0.5),
    ]
    report = build_report(rows)
    assert report.total_values == 3
    assert report.compared_values == 2
    assert report.overall_extraction_accuracy == 0.5
    assert report.by_metric["revenue"] == 1.0
    assert report.by_metric["net_income"] == 0.0
    assert report.missing_truth == ["TEST:total_assets:2025"]


def test_escalation_precision_and_calibration():
    rows = [
        _row(Metric.REVENUE, truth=100.0, extracted=90.0, confidence=0.99),
        _row(
            Metric.NET_INCOME,
            truth=10.0,
            extracted=11.0,
            confidence=0.55,
            escalated=True,
            justified=True,
            note="failed: accounting_equation",
        ),
        _row(
            Metric.TOTAL_ASSETS,
            truth=5.0,
            extracted=5.0,
            confidence=0.95,
            escalated=True,
            justified=False,
            note="escalated",
        ),
    ]
    report = build_report(rows)
    assert report.escalated_count == 2
    assert report.auto_approved_count == 1
    assert report.escalation_precision == 0.5
    assert report.by_company["TEST"] == 1 / 3
    low = next(b for b in report.calibration if b.lower == 0.0)
    assert low.count == 1 and low.accuracy == 0.0
    high = next(b for b in report.calibration if b.lower == 0.95)
    assert high.count == 2 and high.accuracy == 0.5

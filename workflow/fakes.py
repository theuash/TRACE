"""Person 2 stand-ins for Person 1 and Person 3, so the graph never waits on a teammate.

Names match `shared.interfaces.FAKES` exactly. Figures are real Apple FY2024 / FY2023 values in FULL
units, so the accounting check behaves as it will against a live filing.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal

from shared.schemas import (
    AccuracyReport,
    AccuracyRow,
    CalibrationBucket,
    Company,
    ExtractedMetric,
    ExtractionResult,
    Extractor,
    FilingRef,
    Metric,
    SegmentTable,
    SegmentValue,
    SourceEvidence,
    ValidationResult,
)

CALLS: Counter[str] = Counter()
PERIOD_END = date(2024, 9, 28)
PERIOD_START = date(2023, 10, 1)

# metric -> (FY2024, FY2023), USD full units
FIGURES: dict[Metric, tuple[str, str]] = {
    Metric.REVENUE: ("391035000000", "383285000000"),
    Metric.NET_INCOME: ("93736000000", "96995000000"),
    Metric.TOTAL_ASSETS: ("364980000000", "352583000000"),
    Metric.TOTAL_LIABILITIES: ("308030000000", "290437000000"),
    Metric.SHAREHOLDERS_EQUITY: ("56950000000", "62146000000"),
    Metric.OPERATING_CASH_FLOW: ("118254000000", "110543000000"),
    Metric.OPERATING_INCOME: ("123216000000", "114301000000"),
    Metric.CASH_AND_EQUIVALENTS: ("29943000000", "29965000000"),
}

# Deterministic parse-quality scores; everything is green except cash, which pauses.
CONFIDENCE: dict[Metric, float] = {
    Metric.REVENUE: 0.96,
    Metric.NET_INCOME: 0.95,
    Metric.TOTAL_ASSETS: 0.94,
    Metric.TOTAL_LIABILITIES: 0.92,
    Metric.SHAREHOLDERS_EQUITY: 0.91,
    Metric.OPERATING_CASH_FLOW: 0.90,
    Metric.OPERATING_INCOME: 0.88,
    Metric.CASH_AND_EQUIVALENTS: 0.78,
}

FLOW = {Metric.REVENUE, Metric.NET_INCOME, Metric.OPERATING_CASH_FLOW, Metric.OPERATING_INCOME}

_CIK = "0000320193"


def _company(ticker: str = "AAPL") -> Company:
    return Company(ticker=ticker, name="Apple Inc.", cik=_CIK)


def _filing(company: Company | None = None) -> FilingRef:
    c = company or _company()
    return FilingRef(
        company=c,
        accession_number="0000320193-24-000123",
        filing_date=date(2024, 11, 1),
        fiscal_year=2024,
        period_end=PERIOD_END,
        primary_document="aapl-20240928.htm",
        url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
        local_path="data/filings/AAPL/aapl-20240928.htm",
    )


_SIGNALS = {
    "label_match": 1.0,
    "table_type": 1.0,
    "unit_clarity": 1.0,
    "period_clarity": 1.0,
    "numeric_wellformed": 0.9,
    "extractor_agreement": 1.0,
}


def _evidence(metric: Metric, printed: str) -> SourceEvidence:
    label = metric.value.replace("_", " ").title()
    return SourceEvidence(
        snippet=f"{label} {printed} 352,583 290,437",
        matched_text=printed,
        location=f"Consolidated Statements, row '{label}'",
        table_index=0,
        row_label=label,
    )


def _printed(raw: str) -> str:
    return f"{int(raw) // 1_000_000:,}"


def _metric(metric: Metric, fiscal_year: int, idx: int, confidence: float) -> ExtractedMetric:
    raw = FIGURES[metric][idx]
    return ExtractedMetric(
        ticker="AAPL",
        metric=metric,
        fiscal_year=fiscal_year,
        period_end=PERIOD_END if fiscal_year == 2024 else date(2023, 9, 30),
        period_start=(PERIOD_START if fiscal_year == 2024 else date(2022, 9, 25))
        if metric in FLOW
        else None,
        value=Decimal(raw),
        scale=1_000_000,
        raw_text=_printed(raw),
        extractor=Extractor.TABLE,
        confidence=confidence,
        confidence_signals=dict(_SIGNALS),
        evidence=_evidence(metric, _printed(raw)),
    )


def _segments() -> list[SegmentTable]:
    ev = SourceEvidence(
        snippet="Products 294,866 Services 96,169 Total net sales 391,035",
        matched_text="391,035",
        location="Note: Segment Information",
    )
    return [
        SegmentTable(
            ticker="AAPL",
            fiscal_year=2024,
            total_metric=Metric.REVENUE,
            segments=[
                SegmentValue(name="Products", value=Decimal("294866000000")),
                SegmentValue(name="Services", value=Decimal("96169000000")),
            ],
            reported_total=Decimal("391035000000"),
            evidence=ev,
        )
    ]


def build_extraction(filing: FilingRef | None = None, *, corrupt: bool = False) -> ExtractionResult:
    """The single fake fixture. `corrupt=True` inflates total assets by 1B for validation tests."""
    metrics = [_metric(m, 2024, 0, CONFIDENCE[m]) for m in FIGURES]
    prior = [_metric(m, 2023, 1, CONFIDENCE[m]) for m in FIGURES]
    if corrupt:
        i = next(n for n, m in enumerate(metrics) if m.metric == Metric.TOTAL_ASSETS)
        metrics[i] = metrics[i].model_copy(
            update={"value": metrics[i].value + Decimal("1000000000")}
        )
    return ExtractionResult(
        filing=filing or _filing(),
        metrics=metrics,
        prior_metrics=prior,
        segments=_segments(),
    )


def fetch_filing(company: Company) -> FilingRef:
    CALLS["fetch_filing"] += 1
    return _filing(company)


def extract_filing(filing: FilingRef) -> ExtractionResult:
    CALLS["extract_filing"] += 1
    return build_extraction(filing)


def score_extraction(result: ExtractionResult) -> ExtractionResult:
    """Fakes already carry deterministic scores; this only counts the call."""
    CALLS["score_extraction"] += 1
    return result


def explain_anomaly(validation: ValidationResult, metric: ExtractedMetric | None = None) -> str:
    CALLS["explain_anomaly"] += 1
    return f"Fallback explanation: {validation.detail}"


def verify_company(
    filing: FilingRef,
    final_metrics: list[ExtractedMetric],
    escalated_ids: list[str],
    validations: list[ValidationResult],
) -> list[AccuracyRow]:
    CALLS["verify_company"] += 1
    rows: list[AccuracyRow] = []
    escalated = set(escalated_ids)
    for m in final_metrics:
        truth = Decimal(FIGURES[m.metric][0]) if m.metric in FIGURES else None
        final = m.effective_value
        rows.append(
            AccuracyRow(
                metric_id=m.id,
                ticker=m.ticker,
                metric=m.metric,
                fiscal_year=m.fiscal_year,
                extracted_value=m.value,
                final_value=final,
                truth_value=truth,
                xbrl_tag=f"us-gaap:{m.metric.value.title().replace('_', '')}",
                extraction_correct=None if truth is None else m.value == truth,
                final_correct=None if truth is None else final == truth,
                confidence=m.confidence,
                escalated=m.id in escalated,
                escalation_justified=(m.id in escalated)
                if truth is None
                else (m.id in escalated) and m.value != truth,
            )
        )
    return rows


def build_report(rows: list[AccuracyRow]) -> AccuracyReport:
    CALLS["build_report"] += 1
    compared = [r for r in rows if r.truth_value is not None]
    correct = [r for r in compared if r.extraction_correct]
    esc = [r for r in rows if r.escalated]
    justified = [r for r in esc if r.escalation_justified]
    buckets = [(0.0, 0.6), (0.6, 0.85), (0.85, 0.95), (0.95, 1.01)]
    calibration = []
    for lo, hi in buckets:
        in_bucket = [r for r in compared if lo <= r.confidence < hi]
        hits = [r for r in in_bucket if r.extraction_correct]
        calibration.append(
            CalibrationBucket(
                lower=lo,
                upper=min(hi, 1.0),
                count=len(in_bucket),
                accuracy=(len(hits) / len(in_bucket)) if in_bucket else None,
            )
        )
    return AccuracyReport(
        rows=rows,
        total_values=len(rows),
        compared_values=len(compared),
        overall_extraction_accuracy=(len(correct) / len(compared)) if compared else None,
        final_accuracy=(
            len([r for r in compared if r.final_correct]) / len(compared) if compared else None
        ),
        auto_approved_count=len([r for r in rows if not r.escalated]),
        escalated_count=len(esc),
        escalation_precision=(len(justified) / len(esc)) if esc else None,
        calibration=calibration,
    )


def reset_calls() -> None:
    CALLS.clear()

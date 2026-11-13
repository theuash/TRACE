"""Aggregate per-metric AccuracyRows into the report the scoreboard renders.

Accuracies are fractions in 0..1; the dashboard multiplies by 100 for display. A row without an
XBRL fact is listed in `missing_truth`, never scored as wrong.
"""

from __future__ import annotations

from collections import defaultdict

from shared.schemas import AccuracyReport, AccuracyRow, CalibrationBucket

BUCKETS: tuple[tuple[float, float], ...] = ((0.0, 0.6), (0.6, 0.85), (0.85, 0.95), (0.95, 1.01))


def _mean(values: list[bool]) -> float | None:
    return (sum(1 for v in values if v) / len(values)) if values else None


def _calibration(compared: list[AccuracyRow]) -> list[CalibrationBucket]:
    buckets: list[CalibrationBucket] = []
    for lower, upper in BUCKETS:
        in_bucket = [r for r in compared if lower <= r.confidence < upper]
        buckets.append(
            CalibrationBucket(
                lower=lower,
                upper=min(upper, 1.0),
                count=len(in_bucket),
                accuracy=_mean([bool(r.extraction_correct) for r in in_bucket]),
            )
        )
    return buckets


def build_report(rows: list[AccuracyRow]) -> AccuracyReport:
    compared = [r for r in rows if r.truth_value is not None]
    escalated = [r for r in rows if r.escalated]
    justified = [r for r in escalated if r.escalation_justified]

    by_metric: dict[str, list[bool]] = defaultdict(list)
    by_company: dict[str, list[bool]] = defaultdict(list)
    for row in compared:
        by_metric[row.metric.value].append(bool(row.extraction_correct))
        by_company[row.ticker].append(bool(row.extraction_correct))

    return AccuracyReport(
        rows=rows,
        total_values=len(rows),
        compared_values=len(compared),
        overall_extraction_accuracy=_mean([bool(r.extraction_correct) for r in compared]),
        final_accuracy=_mean(
            [bool(r.final_correct) for r in compared if r.final_value is not None]
        ),
        auto_approved_count=len(rows) - len(escalated),
        escalated_count=len(escalated),
        escalation_precision=(len(justified) / len(escalated)) if escalated else None,
        by_metric={k: _mean(v) or 0.0 for k, v in sorted(by_metric.items())},
        by_company={k: _mean(v) or 0.0 for k, v in sorted(by_company.items())},
        calibration=_calibration(compared),
        missing_truth=[r.metric_id for r in rows if r.truth_value is None],
    )

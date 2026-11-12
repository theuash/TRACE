"""Demo fault injection: corrupt one extracted value before validation sees it.

The workflow calls this right after extraction, so the corrupted number flows through confidence,
validation, decision and audit exactly like a real extraction error would.
"""

from __future__ import annotations

from decimal import Decimal

from shared.schemas import ExtractedMetric, ExtractionResult, FaultSpec


def apply_fault(result: ExtractionResult, fault: FaultSpec) -> ExtractionResult:
    """Inflate or deflate one metric by `delta_pct`, leaving everything else untouched."""
    metrics: list[ExtractedMetric] = []
    hit = False
    for metric in result.metrics:
        if metric.ticker == fault.ticker.upper() and metric.metric == fault.metric:
            delta = metric.value * Decimal(str(fault.delta_pct)) / Decimal(100)
            metric = metric.model_copy(update={"value": metric.value + delta})
            hit = True
        metrics.append(metric)
    note = (
        f"fault injected: {fault.ticker.upper()} {fault.metric.value} {fault.delta_pct:+.1f}%"
        if hit
        else f"fault requested for {fault.ticker.upper()} {fault.metric.value}, not found"
    )
    return result.model_copy(update={"metrics": metrics, "warnings": [*result.warnings, note]})

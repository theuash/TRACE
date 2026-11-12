"""Deterministic parse-quality confidence. No network, no XBRL, no model, no validation result."""

from __future__ import annotations

import re

from shared.schemas import ExtractedMetric, ExtractionResult, Extractor

WEIGHTS: dict[str, float] = {
    "label_match": 0.25,
    "numeric_wellformed": 0.20,
    "unit_clarity": 0.15,
    "period_clarity": 0.15,
    "table_type": 0.15,
    "extractor_agreement": 0.10,
}
DERIVED_CAP = 0.80
DISAGREEMENT_CAP = 0.70
_CLEAN_RE = re.compile(r"[\s$\u00a0,()]")


def snippet_verbatim(metric: ExtractedMetric) -> float:
    """Is the printed value really in the evidence we show the reviewer?"""
    snippet = metric.evidence.snippet
    printed = metric.evidence.matched_text
    if not printed:
        return 0.2
    if printed in snippet:
        return 1.0
    if _CLEAN_RE.sub("", printed) in _CLEAN_RE.sub("", snippet):
        return 0.6
    return 0.2


def score_metric(metric: ExtractedMetric) -> ExtractedMetric:
    signals = dict(metric.confidence_signals)
    base = signals.get("numeric_wellformed", 0.5)
    signals["numeric_wellformed"] = round(0.6 * base + 0.4 * snippet_verbatim(metric), 4)
    score = sum(weight * signals.get(key, 0.5) for key, weight in WEIGHTS.items())
    if metric.extractor is Extractor.DERIVED:
        score = min(score, DERIVED_CAP)
    if signals.get("extractor_agreement", 0.5) < 0.5:
        score = min(score, DISAGREEMENT_CAP)
    return metric.model_copy(update={"confidence": round(score, 4), "confidence_signals": signals})


def score_extraction(result: ExtractionResult) -> ExtractionResult:
    """Fill `confidence` and `confidence_signals` on every metric. Idempotent by construction."""
    return result.model_copy(
        update={
            "metrics": [score_metric(metric) for metric in result.metrics],
            "prior_metrics": [score_metric(metric) for metric in result.prior_metrics],
        }
    )

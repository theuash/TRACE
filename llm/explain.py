"""The single always-on model call: one plain-English sentence about a failed check."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from llm.client import complete_text
from shared.config import get_settings
from shared.schemas import CheckName, ExtractedMetric, Severity, ValidationResult

SYSTEM = (
    "You explain failed accounting checks on numbers extracted from a US 10-K. "
    "Two sentences maximum. Plain English. Never suggest a new value."
)
EXPLAIN_TIMEOUT_S = 10.0
_unavailable = False  # one dead model must not stall every later check
FALLBACK_BY_CHECK = {
    CheckName.ACCOUNTING_EQUATION: (
        "The accounting equation does not balance. One of the three values was probably read "
        "from the wrong row or column, or the company reports a differently defined metric."
    ),
    CheckName.SEGMENT_SUM: (
        "The segment rows do not add up to the reported total. A segment may be missing from the "
        "table, or a subtotal row may have been read as a segment."
    ),
    CheckName.YOY_CHANGE: (
        "This value moved more than the allowed year-on-year threshold. A large jump can be real, "
        "but it can also mean the wrong column was read."
    ),
}


def _fallback(validation: ValidationResult, metric: ExtractedMetric | None) -> str:
    sentence = FALLBACK_BY_CHECK.get(validation.check, "This check failed.")
    parts = [sentence]
    if validation.detail:
        parts.append(f"Detail: {validation.detail}")
    if metric is not None:
        parts.append(f"Read from '{metric.evidence.location}' as {metric.raw_text}.")
    return " ".join(parts)


def build_prompt(validation: ValidationResult, metric: ExtractedMetric | None) -> str:
    payload = {
        "check": validation.check.value,
        "detail": validation.detail,
        "expected": str(validation.expected) if validation.expected is not None else None,
        "actual": str(validation.actual) if validation.actual is not None else None,
        "difference_pct": validation.difference_pct,
        "metric": None
        if metric is None
        else {
            "name": metric.metric.value,
            "value": str(metric.value),
            "as_printed": metric.raw_text,
            "source": metric.evidence.location,
        },
    }
    return "Explain why this check failed, for a reviewer.\n" + json.dumps(payload, indent=2)


def _tidy(text: str) -> str:
    clean = " ".join(text.replace("\n", " ").split())
    sentences = [part.strip() for part in re.findall(r"[^.!?]+[.!?]", clean)]
    return " ".join(sentences[:2]).strip() or clean


@lru_cache(maxsize=256)
def _explain_cached(validation_json: str, metric_json: str) -> str:
    validation = ValidationResult.model_validate_json(validation_json)
    metric = ExtractedMetric.model_validate_json(metric_json) if metric_json else None
    prompt = build_prompt(validation, metric)
    return _tidy(
        complete_text(
            prompt,
            system=SYSTEM,
            model=get_settings().llm_model_explain,
            max_tokens=120,
            timeout=EXPLAIN_TIMEOUT_S,
        )
    )


def explain_anomaly(validation: ValidationResult, metric: ExtractedMetric | None = None) -> str:
    """Never raises. Falls back to a deterministic sentence when no model is reachable."""
    global _unavailable
    if validation.passed or validation.severity is Severity.INFO:
        return ""
    if _unavailable:
        return _fallback(validation, metric)
    try:
        text = _explain_cached(
            validation.model_dump_json(),
            metric.model_dump_json() if metric is not None else "",
        )
    except Exception:
        _unavailable = True  # one dead model must not stall every later check
        return _fallback(validation, metric)
    return text or _fallback(validation, metric)


def reset_unavailable() -> None:
    global _unavailable
    _unavailable = False

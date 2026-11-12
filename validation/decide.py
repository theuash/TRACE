"""Turns extracted metrics plus validation results into the three-tier decision.

The tier comes from BOTH axes, never from confidence alone:

|                    | all checks pass | warning failure | error failure |
|--------------------|-----------------|-----------------|---------------|
| conf >= green      | GREEN           | YELLOW          | RED           |
| critical <= conf   | YELLOW          | YELLOW          | RED           |
| conf < critical    | RED             | RED             | RED           |

A failed check escalates every metric named in `ValidationResult.metric_ids`. That is the math
override: no confidence score can outvote a broken balance sheet.
"""

from __future__ import annotations

from shared.interfaces import load_provider
from shared.schemas import (
    CORE_METRICS,
    AutoDecision,
    EscalationItem,
    EscalationKind,
    EscalationReason,
    ExtractedMetric,
    ExtractionResult,
    Metric,
    RiskTier,
    Severity,
    SourceEvidence,
    Thresholds,
    ValidationResult,
    make_metric_id,
)

# (metric_id, check) -> sentence. Survives within a process; across a restart the sentence is
# already stored on the ValidationResult, so `decide` never calls the model twice for one failure.
_CACHE: dict[tuple[str, str], str] = {}


def reset_explain_cache() -> None:
    _CACHE.clear()


def _template(validation: ValidationResult) -> str:
    """Deterministic fallback. This is what ships when no model is reachable."""
    check = validation.check.value.replace("_", " ")
    return f"{check.capitalize()} failed: {validation.detail}"


def explain(validation: ValidationResult, metric: ExtractedMetric | None) -> str:
    """One sentence per failed check, cached by (metric_id, check)."""
    if validation.explanation:
        return validation.explanation
    key = (metric.id if metric else validation.ticker, validation.check.value)
    if key in _CACHE:
        return _CACHE[key]
    try:
        sentence = load_provider("explain_anomaly")(validation, metric)
    except Exception:  # noqa: BLE001 - the explainer must never break a decision
        sentence = _template(validation)
    sentence = (sentence or "").strip() or _template(validation)
    _CACHE[key] = sentence
    validation.explanation = sentence
    return sentence


def tier_for(
    metric: ExtractedMetric, failed: list[ValidationResult], thresholds: Thresholds
) -> RiskTier:
    """The single place a colour is decided. The UI renders it; it never recomputes it."""
    green = thresholds.confidence_for(metric.metric)
    if any(v.severity == Severity.ERROR for v in failed) or (
        metric.confidence < thresholds.confidence_critical
    ):
        return RiskTier.RED
    if failed or metric.confidence < green:
        return RiskTier.YELLOW
    return RiskTier.GREEN


def _reasons(
    metric: ExtractedMetric, failed: list[ValidationResult], thresholds: Thresholds
) -> list[EscalationReason]:
    reasons: list[EscalationReason] = []
    green = thresholds.confidence_for(metric.metric)
    if metric.confidence < green:
        reasons.append(
            EscalationReason(
                kind=EscalationKind.LOW_CONFIDENCE,
                message=f"Confidence {metric.confidence:.2f} is below the {green:.2f} threshold.",
            )
        )
    if metric.confidence_signals.get("extractor_agreement", 1.0) < 0.5:
        reasons.append(
            EscalationReason(
                kind=EscalationKind.EXTRACTOR_DISAGREEMENT,
                message="The two extractors disagreed on this value.",
            )
        )
    for validation in failed:
        reasons.append(
            EscalationReason(
                kind=EscalationKind.VALIDATION_FAILED,
                message=explain(validation, metric),
            )
        )
    return reasons


def _missing_item(result: ExtractionResult, metric: Metric) -> EscalationItem:
    """A core metric that is absent from the filing. Always Red: absence beats any confidence."""
    filing = result.filing
    label = metric.value.replace("_", " ").capitalize()
    return EscalationItem(
        review_id=make_metric_id(filing.company.ticker, metric, filing.fiscal_year),
        ticker=filing.company.ticker,
        metric=metric,
        fiscal_year=filing.fiscal_year,
        value=None,  # no number exists; writing 0 would invent one
        confidence=0.0,
        tier=RiskTier.RED,
        reasons=[
            EscalationReason(
                kind=EscalationKind.MISSING_VALUE,
                message=f"{label} was not found in this filing.",
            )
        ],
        evidence=SourceEvidence(
            snippet="",
            matched_text="",
            location=f"not found in {filing.primary_document}",
            source_url=filing.url,
        ),
    )


def decide(
    result: ExtractionResult,
    validations: list[ValidationResult],
    thresholds: Thresholds,
) -> AutoDecision:
    """Auto-approve the Green values, escalate the Yellow and Red ones with reasons."""
    failed_by_metric: dict[str, list[ValidationResult]] = {}
    for validation in validations:
        if validation.passed:
            continue
        for metric_id in validation.metric_ids:
            failed_by_metric.setdefault(metric_id, []).append(validation)

    approved: list[str] = []
    escalations: list[EscalationItem] = []
    present = {metric.metric for metric in result.metrics}
    for metric in result.metrics:
        failed = failed_by_metric.get(metric.id, [])
        tier = tier_for(metric, failed, thresholds)
        if tier == RiskTier.GREEN:
            approved.append(metric.id)
            continue
        escalations.append(
            EscalationItem(
                review_id=metric.id,
                ticker=metric.ticker,
                metric=metric.metric,
                fiscal_year=metric.fiscal_year,
                value=metric.value,
                unit=metric.unit,
                confidence=metric.confidence,
                tier=tier,
                reasons=_reasons(metric, failed, thresholds),
                evidence=metric.evidence,
                failed_checks=failed,
            )
        )
    escalations.extend(
        _missing_item(result, metric) for metric in CORE_METRICS if metric not in present
    )
    escalations.sort(key=lambda item: (item.tier != RiskTier.RED, item.confidence))
    return AutoDecision(auto_approved_ids=approved, escalations=escalations)

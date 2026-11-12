import pytest

from shared.schemas import (
    CheckName,
    ExtractedMetric,
    Metric,
    RiskTier,
    Severity,
    Thresholds,
    ValidationResult,
    make_metric_id,
)
from validation.decide import decide, reset_explain_cache, tier_for
from workflow.fakes import CALLS, build_extraction, reset_calls

T = Thresholds()


def _metric(confidence: float) -> ExtractedMetric:
    return (
        build_extraction()
        .current(Metric.TOTAL_ASSETS)
        .model_copy(update={"confidence": confidence})
    )


def _check(severity: Severity) -> ValidationResult:
    return ValidationResult(
        ticker="AAPL",
        fiscal_year=2024,
        check=CheckName.YOY_CHANGE,
        passed=False,
        severity=severity,
        detail="test",
        metric_ids=[make_metric_id("AAPL", Metric.TOTAL_ASSETS, 2024)],
    )


@pytest.mark.parametrize(
    ("confidence", "failure", "expected"),
    [
        (0.95, None, RiskTier.GREEN),
        (0.95, Severity.WARNING, RiskTier.YELLOW),
        (0.95, Severity.ERROR, RiskTier.RED),
        (0.70, None, RiskTier.YELLOW),
        (0.70, Severity.WARNING, RiskTier.YELLOW),
        (0.70, Severity.ERROR, RiskTier.RED),
        (0.55, None, RiskTier.RED),
        (0.55, Severity.WARNING, RiskTier.RED),
    ],
)
def test_tier_matrix_combines_both_axes(confidence, failure, expected):
    failed = [] if failure is None else [_check(failure)]
    assert tier_for(_metric(confidence), failed, T) is expected


def test_math_override_beats_a_high_confidence_score():
    from validation.engine import run_validations

    reset_explain_cache()
    result = build_extraction(corrupt=True)
    decision = decide(result, run_validations(result, T), T)
    red = [e for e in decision.escalations if e.tier is RiskTier.RED]
    assert {e.metric for e in red} == {
        Metric.TOTAL_ASSETS,
        Metric.TOTAL_LIABILITIES,
        Metric.SHAREHOLDERS_EQUITY,
    }
    assert all(e.confidence >= 0.90 for e in red)


def test_explainer_is_called_once_per_failed_check():
    from validation.engine import run_validations

    reset_explain_cache()
    reset_calls()
    result = build_extraction(corrupt=True)
    validations = run_validations(result, T)
    decide(result, validations, T)
    first = CALLS["explain_anomaly"]
    assert first == 1
    decide(result, validations, T)
    assert CALLS["explain_anomaly"] == first


def test_missing_core_metric_is_red_and_carries_no_value():
    from validation.engine import run_validations

    reset_explain_cache()
    result = build_extraction()
    keep = [m for m in result.metrics if m.metric not in (Metric.REVENUE, Metric.TOTAL_ASSETS)]
    result = result.model_copy(update={"metrics": keep})

    decision = decide(result, run_validations(result, T), T)
    missing = [e for e in decision.escalations if e.metric in (Metric.REVENUE, Metric.TOTAL_ASSETS)]

    assert {e.metric for e in missing} == {Metric.REVENUE, Metric.TOTAL_ASSETS}
    assert all(e.tier is RiskTier.RED for e in missing)
    assert all(e.value is None for e in missing)  # absence is never 0
    assert all(e.reasons[0].kind.value == "missing_value" for e in missing)
    assert not set(e.review_id for e in missing) & set(decision.auto_approved_ids)


def test_green_values_are_auto_approved():
    from validation.engine import run_validations

    reset_explain_cache()
    result = build_extraction()
    decision = decide(result, run_validations(result, T), T)
    assert len(decision.auto_approved_ids) == 7
    assert [e.metric.value for e in decision.escalations] == ["cash_and_equivalents"]

from decimal import Decimal

from shared.schemas import CheckName, Metric, Severity, Thresholds
from validation.engine import run_validations
from workflow.fakes import build_extraction

T = Thresholds()


def _failed(results):
    return [r for r in results if not r.passed]


def test_clean_filing_passes_every_check():
    results = run_validations(build_extraction(), T)
    assert len(results) == 10
    assert _failed(results) == []
    assert {r.check for r in results} == set(CheckName)


def test_corrupt_assets_trips_only_the_accounting_equation():
    results = run_validations(build_extraction(corrupt=True), T)
    failed = _failed(results)
    assert [r.check for r in failed] == [CheckName.ACCOUNTING_EQUATION]
    assert failed[0].severity is Severity.ERROR
    assert len(failed[0].metric_ids) == 3
    assert "off by" in failed[0].detail


def test_yoy_is_a_warning_and_missing_prior_is_an_error():
    result = build_extraction()
    result = result.model_copy(
        update={
            "prior_metrics": [m for m in result.prior_metrics if m.metric is not Metric.REVENUE]
        }
    )
    failed = [r for r in run_validations(result, T) if not r.passed]
    assert [r.check for r in failed] == [CheckName.YOY_CHANGE]
    assert failed[0].severity is Severity.ERROR
    assert "no prior-year value" in failed[0].detail


def test_segment_sum_tolerance_is_respected():
    result = build_extraction()
    table = result.segments[0].model_copy(update={"reported_total": Decimal("391035500000")})
    results = run_validations(result.model_copy(update={"segments": [table]}), T)
    assert all(r.passed for r in results if r.check is CheckName.SEGMENT_SUM)

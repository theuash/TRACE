"""The three mandatory checks.

Each returns a `ValidationResult` with a plain-English `detail`. They are pure functions of the
extracted values and the thresholds: no network, no LLM, no ground truth. A failed check names every
metric involved in `metric_ids`, because `decide()` escalates all of them.
"""

from __future__ import annotations

from decimal import Decimal

from shared.schemas import (
    CheckName,
    ExtractionResult,
    Metric,
    Severity,
    Thresholds,
    ValidationResult,
)


def human(value: Decimal | None) -> str:
    """Compact money for a reviewer: 364.98B, 1.20M, 12.00."""
    if value is None:
        return "missing"
    v = Decimal(value)
    for limit, suffix in (
        (Decimal("1e12"), "T"),
        (Decimal("1e9"), "B"),
        (Decimal("1e6"), "M"),
    ):
        if abs(v) >= limit:
            return f"{v / limit:,.2f}{suffix}"
    return f"{v:,.2f}"


def pct_gap(actual: Decimal, expected: Decimal) -> float:
    """Absolute difference as a percentage of `expected`; 0.0 when both are zero."""
    if expected == 0:
        return 0.0 if actual == 0 else 100.0
    return float(abs(actual - expected) / abs(expected) * 100)


def _result(
    result: ExtractionResult,
    check: CheckName,
    passed: bool,
    severity: Severity,
    detail: str,
    metric_ids: list[str],
    *,
    expected: Decimal | None = None,
    actual: Decimal | None = None,
    difference_pct: float | None = None,
) -> ValidationResult:
    return ValidationResult(
        ticker=result.filing.company.ticker,
        fiscal_year=result.filing.fiscal_year,
        check=check,
        passed=passed,
        severity=Severity.INFO if passed else severity,
        detail=detail,
        metric_ids=metric_ids,
        expected=expected,
        actual=actual,
        difference_pct=difference_pct,
    )


def _current_ids(result: ExtractionResult, *metrics: Metric) -> list[str]:
    return [m.id for m in (result.current(x) for x in metrics) if m is not None]


def _missing_labels(result: ExtractionResult, *metrics: Metric) -> str:
    return ", ".join(x.value for x in metrics if result.current(x) is None)


def accounting_equation(result: ExtractionResult, thresholds: Thresholds) -> list[ValidationResult]:
    """Assets = Liabilities + Equity. An `error` here always wins over a high confidence score."""
    assets = result.current(Metric.TOTAL_ASSETS)
    liab = result.current(Metric.TOTAL_LIABILITIES)
    equity = result.current(Metric.SHAREHOLDERS_EQUITY)
    ids = _current_ids(
        result, Metric.TOTAL_ASSETS, Metric.TOTAL_LIABILITIES, Metric.SHAREHOLDERS_EQUITY
    )
    if assets is None or liab is None or equity is None:
        missing = _missing_labels(
            result, Metric.TOTAL_ASSETS, Metric.TOTAL_LIABILITIES, Metric.SHAREHOLDERS_EQUITY
        )
        return [
            _result(
                result,
                CheckName.ACCOUNTING_EQUATION,
                False,
                Severity.ERROR,
                f"Balance sheet cannot be checked: {missing} is missing.",
                ids,
            )
        ]
    expected = liab.value + equity.value
    gap = pct_gap(assets.value, expected)
    passed = gap <= thresholds.accounting_tolerance_pct
    sign = "=" if passed else "!="
    detail = (
        f"Assets ({human(assets.value)}) {sign} liabilities ({human(liab.value)}) "
        f"+ equity ({human(equity.value)}); off by {gap:.2f}% "
        f"(tolerance {thresholds.accounting_tolerance_pct:.2f}%)."
    )
    return [
        _result(
            result,
            CheckName.ACCOUNTING_EQUATION,
            passed,
            Severity.ERROR,
            detail,
            ids,
            expected=expected,
            actual=assets.value,
            difference_pct=gap,
        )
    ]


def segment_sum(result: ExtractionResult, thresholds: Thresholds) -> list[ValidationResult]:
    """Segments must add up to the reported total. Skipped when the filing has no segment table."""
    out: list[ValidationResult] = []
    for table in result.segments:
        total = sum((s.value for s in table.segments), Decimal(0))
        gap = pct_gap(total, table.reported_total)
        passed = gap <= thresholds.segment_tolerance_pct
        metric = result.current(table.total_metric)
        detail = (
            f"Segments add up to {human(total)} but {table.total_metric.value} is reported as "
            f"{human(table.reported_total)}; off by {gap:.2f}%."
        )
        out.append(
            _result(
                result,
                CheckName.SEGMENT_SUM,
                passed,
                Severity.ERROR,
                detail,
                [metric.id] if metric else [],
                expected=table.reported_total,
                actual=total,
                difference_pct=gap,
            )
        )
    return out


def yoy_change(result: ExtractionResult, thresholds: Thresholds) -> list[ValidationResult]:
    """A jump larger than the threshold is a `warning`: suspicious, not necessarily wrong."""
    out: list[ValidationResult] = []
    for m in result.metrics:
        prior = result.prior(m.metric)
        if prior is None:
            out.append(
                _result(
                    result,
                    CheckName.YOY_CHANGE,
                    False,
                    Severity.ERROR,
                    f"{m.metric.value} has no prior-year value, so year-on-year cannot be checked.",
                    [m.id],
                )
            )
            continue
        if prior.value == 0:
            out.append(
                _result(
                    result,
                    CheckName.YOY_CHANGE,
                    False,
                    Severity.ERROR,
                    f"{m.metric.value} was zero last year, so the change is undefined.",
                    [m.id],
                )
            )
            continue
        change = float((m.value - prior.value) / abs(prior.value) * 100)
        moved = "rose" if change >= 0 else "fell"
        passed = abs(change) <= thresholds.yoy_change_pct
        detail = (
            f"{m.metric.value} {moved} {abs(change):.1f}% year on year "
            f"({human(prior.value)} to {human(m.value)}; limit {thresholds.yoy_change_pct:.0f}%)."
        )
        out.append(
            _result(
                result,
                CheckName.YOY_CHANGE,
                passed,
                Severity.WARNING,
                detail,
                [m.id],
                expected=prior.value,
                actual=m.value,
                difference_pct=abs(change),
            )
        )
    return out

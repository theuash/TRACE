"""Runs every validation check and returns passed AND failed results.

`decide()` needs both: the pass list justifies a Green tier, the fail list escalates.
"""

from __future__ import annotations

from collections.abc import Callable

from shared.schemas import ExtractionResult, Thresholds, ValidationResult
from validation import checks

Runner = Callable[[ExtractionResult, Thresholds], list[ValidationResult]]

RUNNERS: tuple[Runner, ...] = (
    checks.accounting_equation,
    checks.segment_sum,
    checks.yoy_change,
)


def run_validations(result: ExtractionResult, thresholds: Thresholds) -> list[ValidationResult]:
    """All three checks, in a stable order, passed and failed."""
    out: list[ValidationResult] = []
    for runner in RUNNERS:
        out.extend(runner(result, thresholds))
    return out

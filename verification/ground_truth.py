"""Compare extraction (and the human's final value) against XBRL Company Facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from shared.config import get_settings
from shared.schemas import AccuracyRow, ExtractedMetric, FilingRef, Metric, ValidationResult
from verification import tag_map, xbrl_client


@dataclass(frozen=True)
class _Period:
    """The two facts verification needs about a filing: when it ended and which year it is."""

    period_end: date
    fiscal_year: int


def _close(left: Decimal, right: Decimal, tolerance_pct: float) -> bool:
    """Relative comparison; a clean parse of the same filing should agree exactly."""
    if right == 0:
        return left == 0
    return abs(left - right) <= abs(right) * (Decimal(str(tolerance_pct)) / Decimal(100))


def _facts(payload: dict[str, Any], tag: str, unit: str) -> list[dict[str, Any]]:
    gaap = payload.get("facts", {}).get("us-gaap", {})
    return gaap.get(tag, {}).get("units", {}).get(unit, [])


def _pick(
    payload: dict[str, Any], metric: Metric, filing: FilingRef | _Period
) -> tuple[str, Decimal] | None:
    """Best tag for this period: exact period end first, then the most specific tag in TAG_MAP."""
    unit = tag_map.unit_for(metric)
    tags = tag_map.tags_for(metric)
    best: tuple[int, int, str, Decimal] | None = None
    best_tag = None
    for index, tag in enumerate(tags):
        for fact in _facts(payload, tag, unit):
            if not str(fact.get("form", "")).startswith("10-K"):
                continue
            try:
                end = date.fromisoformat(str(fact["end"]))
            except (KeyError, ValueError):
                continue
            exact = end == filing.period_end
            near = abs((end - filing.period_end).days) <= 7
            if not (exact or near or fact.get("fy") == filing.fiscal_year):
                continue
            rank = 2 if exact else (1 if near else 0)
            candidate = (
                rank,
                -index,  # earlier tags in TAG_MAP are more specific
                str(fact.get("filed", "")),
                Decimal(str(fact["val"])),
            )
            if best is None or candidate > best:
                best, best_tag = candidate, tag
    return (best_tag, best[3]) if best and best_tag else None


def _failed_checks(metric_id: str, validations: list[ValidationResult]) -> list[str]:
    return [v.check.value for v in validations if not v.passed and metric_id in v.metric_ids]


def _row(
    metric: ExtractedMetric,
    truth: tuple[str, Decimal] | None,
    escalated: bool,
    validations: list[ValidationResult],
    tolerance_pct: float,
) -> AccuracyRow:
    tag, truth_value = truth if truth else (None, None)
    extracted = metric.value
    final = metric.effective_value
    extraction_correct = (
        None if truth_value is None else _close(extracted, truth_value, tolerance_pct)
    )
    final_correct = (
        None if truth_value is None or final is None else _close(final, truth_value, tolerance_pct)
    )
    failed = _failed_checks(metric.id, validations)
    justified = None
    if escalated:
        justified = extraction_correct is False or bool(failed)
    notes: list[str] = []
    if failed:
        notes.append("failed: " + ", ".join(failed))
    if truth_value is None:
        notes.append("no XBRL fact")
    if escalated:
        notes.append("escalated")
    return AccuracyRow(
        metric_id=metric.id,
        ticker=metric.ticker,
        metric=metric.metric,
        fiscal_year=metric.fiscal_year,
        extracted_value=extracted,
        final_value=final,
        truth_value=truth_value,
        xbrl_tag=tag,
        extraction_correct=extraction_correct,
        final_correct=final_correct,
        confidence=metric.confidence,
        escalated=escalated,
        escalation_justified=justified,
        note="; ".join(notes) or None,
    )


def verify_company(
    filing: FilingRef,
    final_metrics: list[ExtractedMetric],
    escalated_ids: list[str],
    validations: list[ValidationResult],
) -> list[AccuracyRow]:
    """One row per extracted metric. Never raises: a missing answer key is recorded, not hidden."""
    return verify_company_values(
        cik=filing.company.cik,
        period_end=filing.period_end,
        fiscal_year=filing.fiscal_year,
        final_metrics=final_metrics,
        escalated_ids=escalated_ids,
        validations=validations,
    )


def verify_company_values(
    *,
    cik: str,
    period_end: date,
    fiscal_year: int,
    final_metrics: list[ExtractedMetric],
    escalated_ids: list[str],
    validations: list[ValidationResult],
) -> list[AccuracyRow]:
    """Same verification without a FilingRef.

    The API layer knows the CIK, the period end and the fiscal year of a run but not the
    accession number, so it can only build the answer key - which is all verification needs.
    """
    tolerance = get_settings().accuracy_tolerance_pct
    escalated = set(escalated_ids)
    try:
        payload = xbrl_client.fetch_company_facts(cik)
    except xbrl_client.XbrlUnavailable:
        payload = {}
    filing = _Period(period_end=period_end, fiscal_year=fiscal_year)
    rows: list[AccuracyRow] = []
    for metric in final_metrics:
        truth = _pick(payload, metric.metric, filing) if payload else None
        rows.append(_row(metric, truth, metric.id in escalated, validations, tolerance))
    return rows

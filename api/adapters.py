"""Map backend contracts (`shared.schemas`) to the JSON shape `trace-ui/src/api/types.ts` expects.

The UI never computes a tier or a statistic: every value here comes from the service. This module
is the only place that knows both vocabularies, so a UI type change is a one-file change.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from shared.config import get_company, register_company
from shared.schemas import (
    AccuracyReport,
    AuditEntry,
    EscalationItem,
    ExtractedMetric,
    Metric,
    RiskTier,
    RunStatus,
    RunSummary,
    Step,
    Thresholds,
    ValidationResult,
)

LABELS: dict[Metric, str] = {
    Metric.REVENUE: "Revenue",
    Metric.NET_INCOME: "Net Income",
    Metric.TOTAL_ASSETS: "Total Assets",
    Metric.TOTAL_LIABILITIES: "Total Liabilities",
    Metric.SHAREHOLDERS_EQUITY: "Shareholders' Equity",
    Metric.OPERATING_CASH_FLOW: "Operating Cash Flow",
    Metric.OPERATING_INCOME: "Operating Income",
    Metric.CASH_AND_EQUIVALENTS: "Cash and Cash Equivalents",
    Metric.GROSS_PROFIT: "Gross Profit",
    Metric.DILUTED_EPS: "Diluted EPS",
}

STEP_TO_AUDIT_STATUS: dict[Step, str] = {
    Step.FETCH_FILING: "FETCHED",
    Step.EXTRACT: "EXTRACTED",
    Step.SCORE: "EXTRACTED",
    Step.VALIDATE: "VALIDATED",
    Step.DECIDE: "VALIDATED",
    Step.REVIEW_GATE: "PAUSED_FOR_REVIEW",
    Step.APPLY_DECISIONS: "HUMAN_REVIEWED",
    Step.VERIFY: "AUTO_APPROVED",
    Step.REPORT: "AUTO_APPROVED",
}


def num(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def label(metric: Metric | str) -> str:
    try:
        return LABELS[Metric(metric)]
    except (ValueError, KeyError):
        return str(metric).replace("_", " ").title()


def audit_status(summary: RunSummary) -> str:
    if summary.status == RunStatus.FAILED:
        return "FAILED"
    if summary.status == RunStatus.PAUSED:
        return "PAUSED_FOR_REVIEW"
    if summary.status == RunStatus.COMPLETED:
        return "COMPLETED"
    if summary.status == RunStatus.PENDING:
        return "STARTED"
    return STEP_TO_AUDIT_STATUS.get(summary.current_step, "STARTED")


def confidence_signals(signals: dict[str, float]) -> dict[str, float | None]:
    """The UI's nine slots, filled from the six real parse-quality signals.

    Unknown keys stay `None` so the hover breakdown shows "not measured" rather than a fake 0.
    """
    return {
        "snippet_grounding": signals.get("numeric_wellformed"),
        "concept_match": signals.get("label_match"),
        "unit_consistency": signals.get("unit_clarity"),
        "period_consistency": signals.get("period_clarity"),
        "prior_year_sanity": signals.get("prior_year_sanity"),
        "extractor_agreement": signals.get("extractor_agreement"),
        "column_period": signals.get("period_clarity"),
        "cross_statement": signals.get("table_type"),
        "llm_confidence": signals.get("llm_confidence"),
    }


def decision_state(metric: ExtractedMetric, escalated: bool) -> str:
    status = metric.status.value
    if status == "auto_approved":
        return "AUTO_APPROVED"
    if status in {"approved", "corrected", "rejected"}:
        return status.upper()
    return "FLAGGED" if escalated else "PENDING"


def metric_payload(
    metric: ExtractedMetric,
    *,
    threshold: float,
    prior: ExtractedMetric | None,
    escalated: bool,
) -> dict[str, Any]:
    return {
        "metric_name": label(metric.metric),
        "value_usd": num(metric.value),
        "original_value": num(metric.value),
        "unit": metric.unit.value,
        "period": f"FY{metric.fiscal_year}",
        "prior_year_value_usd": num(prior.value) if prior else None,
        "confidence": metric.confidence,
        "confidence_label": "HIGH" if metric.confidence >= threshold else "LOW",
        "confidence_signals": confidence_signals(metric.confidence_signals),
        "source_snippet": metric.evidence.snippet,
        "matched_text": metric.evidence.matched_text,
        "source_header": metric.evidence.location,
        "source_row": metric.evidence.row_label or "",
        "source_url": metric.evidence.source_url or "",
        "decision_state": decision_state(metric, escalated),
    }


def _escalation_types(item: EscalationItem) -> list[str]:
    kinds = {reason.kind.value for reason in item.reasons}
    out: list[str] = []
    if kinds & {"low_confidence", "missing_value", "extractor_disagreement"}:
        out.append("EXTRACTION_RISK")
    if "validation_failed" in kinds or item.failed_checks:
        out.append("FINANCIAL_ANOMALY")
    return out or ["EXTRACTION_RISK"]


def flagged_payload(
    item: EscalationItem,
    metric: ExtractedMetric | None,
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    severity = {RiskTier.RED: "HIGH", RiskTier.YELLOW: "MEDIUM"}.get(item.tier, "LOW")
    base = (
        metric_payload(metric, threshold=0.0, prior=None, escalated=True)
        if metric is not None
        else {
            "metric_name": label(item.metric),
            "value_usd": None,
            "original_value": None,
            "unit": item.unit.value,
            "period": f"FY{item.fiscal_year}",
            "prior_year_value_usd": None,
            "confidence": item.confidence,
            "confidence_label": "LOW" if item.confidence < 0.85 else "HIGH",
            "confidence_signals": confidence_signals({}),
            "source_snippet": item.evidence.snippet,
            "matched_text": item.evidence.matched_text,
            "source_header": item.evidence.location,
            "source_row": item.evidence.row_label or "",
            "source_url": item.evidence.source_url or "",
            "decision_state": "FLAGGED",
        }
    )
    reasons: list[str] = []
    for check in item.failed_checks:
        # The escalation keeps a trimmed explanation; the full text lives in detail.
        detail = check.detail or ""
        explanation = check.explanation or ""
        text = detail if len(detail) >= len(explanation) else explanation
        text = text.strip()
        if text and text not in reasons:
            reasons.append(text)
    for reason in item.reasons:
        message = reason.message.strip()
        if not message or message in reasons:
            continue
        if message.lower() in {"this check failed", "check failed"}:
            continue
        if any(message.lower() in text.lower() for text in reasons):
            continue
        # A fragment like "The sum of the" is a truncated sentence: the full explanation is
        # already in the list, so keep the list readable.
        if reasons and not (message.endswith((".", ")", "%")) or len(message) >= 40):
            continue
        reasons.append(message)
    return {
        **base,
        "review_id": item.review_id,
        "tier": item.tier.value,
        "reasons": reasons,
        "rules": [check.check.value for check in item.failed_checks],
        "severity": severity,
        "escalation_types": _escalation_types(item),
        # What the human did with this value, straight from the audit log.
        "decided_at": (decision or {}).get("decided_at"),
        "reviewer": (decision or {}).get("reviewer"),
        "reviewer_note": (decision or {}).get("note"),
        "audit_seq": (decision or {}).get("audit_seq"),
        "corrected_value": (decision or {}).get("corrected_value"),
    }


def validation_payload(result: ValidationResult) -> dict[str, Any]:
    first = result.metric_ids[0] if result.metric_ids else ""
    metric_name = label(first.split(":")[1]) if ":" in first else label(first or "filing")
    return {
        "rule_name": result.check.value.replace("_", " ").title(),
        "metric_name": metric_name,
        "status": "PASSED" if result.passed else "FAILED",
        "reason": result.explanation or result.detail,
        "details": result.detail,
        "metrics_involved": [
            label(m.split(":")[1]) if ":" in m else label(m) for m in result.metric_ids
        ],
    }


def thresholds_payload(thresholds: Thresholds) -> dict[str, Any]:
    return {
        "confidence_threshold": thresholds.confidence,
        "confidence_critical": thresholds.confidence_critical,
        "yoy_change_pct": thresholds.yoy_change_pct,
        "accounting_tolerance_pct": thresholds.accounting_tolerance_pct,
        "segment_tolerance_pct": thresholds.segment_tolerance_pct,
    }


def lookup_company(ticker: str | None):
    """The configured five first, then the SEC directory, so any ticker renders a real name."""
    if not ticker:
        return None
    try:
        return get_company(ticker)
    except KeyError:
        pass
    try:
        from extraction import directory

        found = directory.resolve(ticker)
    except Exception:  # noqa: BLE001 - a name lookup must never take a page down
        return None
    return register_company(found) if found else None


def company_name(ticker: str | None) -> str:
    if not ticker:
        return "Unknown"
    company = lookup_company(ticker)
    return company.name if company else ticker


def cik_for(ticker: str | None) -> str:
    company = lookup_company(ticker)
    return company.cik if company else ""


def audit_row(entry: AuditEntry) -> dict[str, Any]:
    decision = (
        entry.decision.value.upper()
        if entry.decision
        else {
            "auto_approval": "AUTO_APPROVED",
            "human_decision": "APPROVED",
            "escalation": "REJECTED",
            "threshold_change": "APPROVED",
        }.get(entry.action.value, "APPROVED")
    )
    metric_name = (
        label(entry.metric_id.split(":")[1]) if entry.metric_id and ":" in entry.metric_id else ""
    )
    if not metric_name:
        # Policy and escalation rows are not about one metric; say what they are about.
        metric_name = {
            "threshold_change": "Policy thresholds",
            "escalation": "Escalation",
        }.get(entry.action.value, "Run")
    return {
        "id": str(entry.seq),
        "thread_id": entry.run_id or "",
        "company_name": company_name(entry.ticker),
        "metric_name": metric_name,
        "decision": decision,
        "original_value": num(entry.original_value),
        "corrected_value": num(entry.corrected_value),
        "reviewer_notes": entry.note or "",
        "action": entry.action.value,
        "timestamp": entry.timestamp.isoformat(),
        "prev_hash": entry.prev_hash,
        "row_hash": entry.hash,
    }


def _pct(value: float | None) -> float:
    return round((value or 0.0) * 100, 2)


def accuracy_payload(report: AccuracyReport) -> dict[str, Any]:
    rows = report.rows
    auto = [r for r in rows if not r.escalated and r.truth_value is not None]
    auto_ok = [r for r in auto if r.final_correct or r.extraction_correct]
    justified = [r for r in rows if r.escalated and r.escalation_justified]
    missed = [
        r
        for r in rows
        if not r.escalated and r.truth_value is not None and r.extraction_correct is False
    ]
    by_type: dict[str, list[bool]] = {"EXTRACTION_RISK": [], "FINANCIAL_ANOMALY": []}
    for row in rows:
        if row.escalated:
            key = "FINANCIAL_ANOMALY" if "failed:" in (row.note or "") else "EXTRACTION_RISK"
            by_type[key].append(bool(row.escalation_justified))
    details = [
        {
            "ticker": row.ticker,
            "metric": label(row.metric),
            "extracted": num(row.extracted_value) or 0.0,
            "final": num(row.final_value) or 0.0,
            "xbrl": num(row.truth_value) or 0.0,
            "match": bool(row.extraction_correct),
            "diff_pct": (
                round(
                    abs(float(row.extracted_value - row.truth_value))
                    / abs(float(row.truth_value))
                    * 100,
                    4,
                )
                if row.truth_value not in (None, 0) and row.extracted_value is not None
                else 0.0
            ),
        }
        for row in rows
        if row.truth_value is not None
    ]
    return {
        "accuracy_pct": _pct(report.final_accuracy),
        "original_accuracy_pct": _pct(report.overall_extraction_accuracy),
        "auto_approval_accuracy_pct": _pct((len(auto_ok) / len(auto)) if auto else None),
        "auto_approved_count": report.auto_approved_count,
        "escalated_count": report.escalated_count,
        "escalation_precision_pct": _pct(report.escalation_precision),
        "escalation_precision_by_type": {
            key: _pct((sum(values) / len(values)) if values else None)
            for key, values in by_type.items()
        },
        "escalation_recall_pct": _pct(
            (len(justified) / (len(justified) + len(missed))) if (justified or missed) else None
        ),
        "per_metric_accuracy": {key: _pct(value) for key, value in report.by_metric.items()},
        "by_company": {key: _pct(value) for key, value in report.by_company.items()},
        "metric_details": details,
        "calibration": [
            {
                "lower": bucket.lower,
                "upper": bucket.upper,
                "count": bucket.count,
                "accuracy": _pct(bucket.accuracy),
            }
            for bucket in report.calibration
        ],
        "missing_truth": report.missing_truth,
    }


def _period(metrics: list[ExtractedMetric]) -> tuple[int | None, str]:
    if not metrics:
        return None, ""
    newest = max(metrics, key=lambda m: m.fiscal_year)
    return newest.fiscal_year, newest.period_end.isoformat()


def thread_payload(summary: RunSummary, metrics: list[ExtractedMetric]) -> dict[str, Any]:
    year, _ = _period(metrics)
    return {
        "thread_id": summary.run_id,
        "company_name": company_name(summary.ticker),
        "ticker": summary.ticker,
        "cik": cik_for(summary.ticker),
        "fiscal_year": year,
        "status": audit_status(summary),
        "flagged_count": summary.escalated,
        "auto_approved_count": summary.auto_approved,
        "created_at": summary.created_at.isoformat(),
        "updated_at": summary.updated_at.isoformat(),
        "pending_reviews": summary.pending_reviews,
        "side_effect_counts": summary.side_effect_counts,
    }


def status_payload(
    summary: RunSummary,
    metrics: list[ExtractedMetric],
    validations: list[ValidationResult],
    flagged: list[EscalationItem],
    accuracy_report: AccuracyReport | None,
    thresholds: Thresholds,
    decisions: dict[str, dict[str, Any]] | None = None,
    audit_corrupt: list[int] | None = None,
) -> dict[str, Any]:
    by_id = {m.id: m for m in metrics}
    escalated_ids = {item.review_id for item in flagged}
    year, period_end = _period(metrics)
    filing_url = next((m.evidence.source_url for m in metrics if m.evidence.source_url), "")
    # Only the current fiscal year is listed; the year before it is the comparison column.
    current = [m for m in metrics if m.fiscal_year == year] if year else list(metrics)
    prior_by_metric = {m.metric: m for m in metrics if year and m.fiscal_year == year - 1}
    return {
        "thread_id": summary.run_id,
        "company_name": company_name(summary.ticker),
        "ticker": summary.ticker,
        "cik": cik_for(summary.ticker),
        "fiscal_year": year or 0,
        "period_end": period_end,
        "filing_url": filing_url or "",
        "status": audit_status(summary),
        "metrics": [
            metric_payload(
                metric,
                threshold=thresholds.confidence_for(metric.metric),
                prior=prior_by_metric.get(metric.metric),
                escalated=metric.id in escalated_ids,
            )
            for metric in current
        ],
        "validation_checks": [validation_payload(v) for v in validations],
        "flagged_items": [
            flagged_payload(item, by_id.get(item.review_id), (decisions or {}).get(item.review_id))
            for item in flagged
        ],
        "anomaly_explanations": {
            v.check.value: {
                "metric_name": label(v.metric_ids[0].split(":")[1]) if v.metric_ids else "",
                "title": v.check.value.replace("_", " ").title(),
                "detail": v.explanation or v.detail,
                "severity": {"error": "HIGH", "warning": "MEDIUM"}.get(v.severity.value, "LOW"),
            }
            for v in validations
            if not v.passed
        },
        "accuracy_report": accuracy_payload(accuracy_report) if accuracy_report else None,
        # Seq numbers of audit rows that could not be read: the chain is broken and the reviewer
        # is told so, instead of the whole status page failing.
        "audit_corrupt": audit_corrupt or [],
        "thresholds": thresholds_payload(thresholds),
        "created_at": summary.created_at.isoformat(),
        "updated_at": summary.updated_at.isoformat(),
        "side_effect_counts": summary.side_effect_counts,
    }

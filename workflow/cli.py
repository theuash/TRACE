"""Run the Person 2 stack from the terminal - no frontend needed.

    uv run python -m workflow.cli            # clean filing: one Yellow pause
    uv run python -m workflow.cli --fault    # injected fault: three Red, guard check

Uses `USE_FAKES=true` unless the env says otherwise.
"""

from __future__ import annotations

import sys

from shared.schemas import (
    DecisionType,
    FaultSpec,
    Metric,
    ReviewDecision,
    ReviewStatus,
    RunRequest,
)
from workflow.service import WorkflowService


def _rule(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 58 - len(title)))


def _print_review(review) -> None:
    line = f"  {review.tier.value.upper():6} {review.metric.value} = {review.value}"
    print(f"{line}  conf {review.confidence:.2f}")
    for reason in review.reasons:
        print(f"         - {reason.kind.value}: {reason.message}")
    print(f"         evidence: {review.evidence.location}")


def main() -> int:
    fault = (
        FaultSpec(ticker="AAPL", metric=Metric.TOTAL_ASSETS, delta_pct=3.0)
        if "--fault" in sys.argv
        else None
    )
    if "--reset" in sys.argv:
        from shared.config import get_settings

        settings = get_settings()
        for db in (
            settings.audit_db_path,
            settings.checkpoint_db_path,
            settings.data_dir / "runs.db",
            settings.data_dir / "idempotency.db",
        ):
            if db.exists():
                db.unlink()
        print("cleared data/*.db")

    service = WorkflowService()

    _rule("START")
    run = service.start_runs(RunRequest(tickers=["AAPL"], fault=fault))[0]
    print(f"run {run.run_id}  status {run.status.value}  metrics {run.total_metrics}")
    print(f"auto-approved {run.auto_approved}  paused on {run.pending_reviews}")
    print(f"side effects so far: {run.side_effect_counts}")

    _rule("PAUSED FOR REVIEW")
    for review in service.list_reviews(ReviewStatus.PENDING):
        _print_review(review)

    _rule("RED GUARD")
    pending = service.list_reviews(ReviewStatus.PENDING)
    red = next((r for r in pending if r.tier.value == "red"), None)
    if red is None:
        print("  no Red value in this run")
    else:
        try:
            service.submit_decision(
                ReviewDecision(
                    review_id=red.review_id, decision=DecisionType.APPROVE, reviewer="cli"
                )
            )
            print("  approved a Red value - the guard did not fire")
        except ValueError as exc:
            print(f"  refused as expected: {exc}")

    _rule("RESUME")
    for review in service.list_reviews(ReviewStatus.PENDING):
        if review.tier.value == "red":
            service.submit_decision(
                ReviewDecision(
                    review_id=review.review_id,
                    decision=DecisionType.EDIT,
                    corrected_value=review.value,
                    reviewer="cli",
                    note="re-read the filing",
                )
            )
        else:
            service.submit_decision(
                ReviewDecision(
                    review_id=review.review_id,
                    decision=DecisionType.APPROVE,
                    reviewer="cli",
                    note="checked in the terminal",
                )
            )
    run = service.get_run(run.run_id)
    print(f"status {run.status.value}  auto-approved {run.auto_approved}")
    print(f"escalated {run.escalated}  pending {run.pending_reviews}")
    print(f"side effects: {run.side_effect_counts}")

    _rule("AUDIT")
    print(f"entries {len(service.list_audit())}  chain verifies: {service.verify_audit().ok}")
    for entry in service.list_audit()[:6]:
        print(f"  #{entry.seq} {entry.actor:8} {entry.action.value:15} {entry.metric_id or ''}")

    _rule("REPORT")
    report = service.get_report()
    if report is None:
        print("  no report")
    else:
        acc = report.overall_extraction_accuracy
        prec = report.escalation_precision
        print(
            f"accuracy {acc:.3f}  escalations {report.escalated_count}  "
            f"precision {prec}  compared {report.compared_values}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

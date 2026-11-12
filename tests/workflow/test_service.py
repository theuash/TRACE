import pytest

from shared.schemas import (
    AuditAction,
    DecisionType,
    FaultSpec,
    Metric,
    ReviewDecision,
    ReviewStatus,
    RiskTier,
    RunRequest,
    RunStatus,
    Thresholds,
)
from workflow.service import WorkflowService


@pytest.fixture()
def svc(tmp_path):
    service = WorkflowService(tmp_path / "runs.db", tmp_path / "ckpt.db")
    yield service
    service._db.close()


def test_run_pauses_then_resumes_without_repeating_a_side_effect(svc):
    run = svc.start_runs(RunRequest(tickers=["AAPL"]))[0]
    assert run.status is RunStatus.PAUSED
    assert run.pending_reviews == 1
    assert run.side_effect_counts["fetch_filing"] == 1
    assert run.side_effect_counts["extract"] == 1

    review = svc.list_reviews(ReviewStatus.PENDING)[0]
    svc.submit_decision(
        ReviewDecision(review_id=review.review_id, decision=DecisionType.APPROVE, reviewer="tester")
    )
    done = svc.get_run(run.run_id)
    assert done.status is RunStatus.COMPLETED
    assert done.pending_reviews == 0
    for step in ("fetch_filing", "extract"):
        assert done.side_effect_counts[step] == run.side_effect_counts[step] == 1
    assert done.side_effect_counts["audit"] == len(svc.list_audit())
    assert svc.verify_audit().ok


def test_failed_resume_is_recorded_on_the_run(svc, monkeypatch):
    """A provider blowing up mid-resume must leave the run FAILED, not a healthy PAUSED."""
    run = svc.start_runs(RunRequest(tickers=["AAPL"]))[0]
    pending = svc.list_reviews(ReviewStatus.PENDING)[0]

    def boom(name):
        raise ModuleNotFoundError(f"No module named {name!r}")

    monkeypatch.setattr("workflow.graph.load_provider", boom)
    with pytest.raises(ModuleNotFoundError):
        svc.submit_decision(
            ReviewDecision(
                review_id=pending.review_id, decision=DecisionType.APPROVE, reviewer="tester"
            )
        )

    failed = svc.get_run(run.run_id)
    assert failed.status is RunStatus.FAILED
    assert "ModuleNotFoundError" in (failed.error or "")


def test_red_value_cannot_be_approved_without_a_note(svc):
    fault = FaultSpec(ticker="AAPL", metric=Metric.TOTAL_ASSETS, delta_pct=3.0)
    run = svc.start_runs(RunRequest(tickers=["AAPL"], fault=fault))[0]
    reds = [r for r in svc.list_reviews(ReviewStatus.PENDING) if r.tier is RiskTier.RED]
    assert len(reds) == 3
    with pytest.raises(ValueError, match="Red"):
        svc.submit_decision(
            ReviewDecision(
                review_id=reds[0].review_id, decision=DecisionType.APPROVE, reviewer="tester"
            )
        )
    svc.submit_decision(
        ReviewDecision(
            review_id=reds[0].review_id,
            decision=DecisionType.APPROVE,
            reviewer="tester",
            note="confirmed against the filing",
        )
    )
    for review in svc.list_reviews(ReviewStatus.PENDING):
        svc.submit_decision(
            ReviewDecision(
                review_id=review.review_id,
                decision=DecisionType.EDIT,
                reviewer="tester",
                corrected_value=review.value,
                note="re-read the table",
            )
        )
    assert svc.get_run(run.run_id).status is RunStatus.COMPLETED
    assert svc.verify_audit().ok
    actions = {entry.action for entry in svc.list_audit()}
    assert {
        AuditAction.AUTO_APPROVAL,
        AuditAction.HUMAN_DECISION,
        AuditAction.ESCALATION,
    } <= actions


def test_threshold_change_is_audited_and_the_estimate_is_a_dry_run(svc):
    svc.start_runs(RunRequest(tickers=["AAPL"]))
    before = len(svc.list_audit())
    estimate = svc.estimate_escalations(Thresholds(confidence=0.99, confidence_critical=0.60))
    assert estimate == 8
    assert len(svc.list_audit()) == before  # a dry run writes nothing

    svc.set_thresholds(Thresholds(confidence=0.90, confidence_critical=0.50), actor="lead")
    changed = [e for e in svc.list_audit() if e.action is AuditAction.THRESHOLD_CHANGE]
    assert len(changed) == 1
    assert changed[0].actor == "lead"
    assert "0.85->0.90" in changed[0].note

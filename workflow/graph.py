"""The LangGraph workflow.

Nodes run in this order:

    fetch_filing -> extract -> score -> validate -> decide -> review_gate
        -> apply_decisions -> verify -> report

State holds JSON-safe dicts, not models, so the SQLite checkpointer can always round-trip it.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.types import interrupt

from audit.log import get_log
from shared.config import get_company
from shared.interfaces import load_provider
from shared.schemas import (
    AccuracyRow,
    AuditAction,
    AutoDecision,
    DecisionType,
    ExtractionResult,
    FaultSpec,
    FilingRef,
    MetricStatus,
    ReviewDecision,
    Step,
    Thresholds,
    ValidationResult,
)
from workflow.fault import apply_fault
from workflow.idempotency import get_store


class GraphState(TypedDict, total=False):
    run_id: str
    ticker: str
    fiscal_year: int
    thresholds: dict[str, Any]
    fault: dict[str, Any] | None
    filing: dict[str, Any]
    extraction: dict[str, Any]
    validations: list[dict[str, Any]]
    decision: dict[str, Any]
    decisions: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    report: dict[str, Any] | None
    steps_completed: list[str]
    error: str | None


def _steps(state: GraphState, step: Step) -> list[str]:
    return [*state.get("steps_completed", []), step.value]


def _thresholds(state: GraphState) -> Thresholds:
    return Thresholds.model_validate(state.get("thresholds") or {})


def _fetch(state: GraphState, store) -> dict[str, Any]:
    step = Step.FETCH_FILING
    company = get_company(state["ticker"])
    filing = store.run_once(
        state["run_id"],
        step.value,
        "run",
        lambda: load_provider("fetch_filing")(company),
        model=FilingRef,
    )
    return {"filing": filing.model_dump(mode="json"), "steps_completed": _steps(state, step)}


def _extract(state: GraphState, store) -> dict[str, Any]:
    step = Step.EXTRACT
    filing = FilingRef.model_validate(state["filing"])
    result = store.run_once(
        state["run_id"],
        step.value,
        "run",
        lambda: load_provider("extract_filing")(filing),
        model=ExtractionResult,
    )
    if state.get("fault"):
        result = apply_fault(result, FaultSpec.model_validate(state["fault"]))
    return {"extraction": result.model_dump(mode="json"), "steps_completed": _steps(state, step)}


def _score(state: GraphState, store) -> dict[str, Any]:
    """Pure transform: no ledger entry needed, but the step is still recorded."""
    step = Step.SCORE
    result = ExtractionResult.model_validate(state["extraction"])
    scored = load_provider("score_extraction")(result)
    return {"extraction": scored.model_dump(mode="json"), "steps_completed": _steps(state, step)}


def _validate(state: GraphState, store) -> dict[str, Any]:
    step = Step.VALIDATE
    result = ExtractionResult.model_validate(state["extraction"])
    validations = load_provider("run_validations")(result, _thresholds(state))
    return {
        "validations": [v.model_dump(mode="json") for v in validations],
        "steps_completed": _steps(state, step),
    }


def _decide(state: GraphState, store) -> dict[str, Any]:
    step = Step.DECIDE
    result = ExtractionResult.model_validate(state["extraction"])
    validations = [ValidationResult.model_validate(v) for v in state.get("validations", [])]
    decision = load_provider("decide")(result, validations, _thresholds(state))
    return {
        "decision": decision.model_dump(mode="json"),
        "steps_completed": _steps(state, step),
    }


def _review_gate(state: GraphState, store) -> dict[str, Any]:
    """The only pause. Nothing is written before `interrupt()`.

    Each `interrupt()` returns the decisions submitted since the last pause, so reviewers can
    answer one at a time: the node re-runs and waits again for the rest.
    """
    step = Step.REVIEW_GATE
    decision = AutoDecision.model_validate(state["decision"])
    known = [ReviewDecision.model_validate(d) for d in state.get("decisions", [])]
    while True:
        answered = {d.review_id for d in known}
        pending = [e for e in decision.escalations if e.review_id not in answered]
        if not pending:
            return {
                "decisions": [d.model_dump(mode="json") for d in known],
                "steps_completed": _steps(state, step),
            }
        resumed = interrupt({"awaiting": len(pending)})
        batch = resumed if isinstance(resumed, list) else [resumed]
        known.extend(ReviewDecision.model_validate(d) for d in batch)


def _apply(state: GraphState, store) -> dict[str, Any]:
    step = Step.APPLY_DECISIONS
    result = ExtractionResult.model_validate(state["extraction"])
    decision = AutoDecision.model_validate(state["decision"])
    decisions = [ReviewDecision.model_validate(d) for d in state.get("decisions", [])]
    by_id = {m.id: m for m in result.metrics}
    for d in decisions:
        metric = by_id.get(d.review_id)
        if metric is None:
            continue
        if d.decision == DecisionType.APPROVE:
            metric.status = MetricStatus.APPROVED
        elif d.decision == DecisionType.EDIT:
            metric.status = MetricStatus.CORRECTED
            metric.reviewed_value = d.corrected_value
        else:
            metric.status = MetricStatus.REJECTED
    for metric_id in decision.auto_approved_ids:
        if metric_id in by_id:
            by_id[metric_id].status = MetricStatus.AUTO_APPROVED
    log = get_log()
    run_id, ticker = state["run_id"], state["ticker"]

    for d in decisions:

        def _human(d: ReviewDecision = d) -> None:
            log.append(
                actor=d.reviewer,
                action=AuditAction.HUMAN_DECISION,
                run_id=run_id,
                ticker=ticker,
                metric_id=d.review_id,
                original_value=by_id[d.review_id].value if d.review_id in by_id else None,
                corrected_value=d.corrected_value,
                decision=d.decision,
                note=d.note,
            )

        store.run_once(run_id, "audit", f"human:{d.review_id}", _human)

    for metric_id in decision.auto_approved_ids:

        def _auto(metric_id: str = metric_id) -> None:
            log.append(
                actor="system",
                action=AuditAction.AUTO_APPROVAL,
                run_id=run_id,
                ticker=ticker,
                metric_id=metric_id,
                original_value=by_id[metric_id].value if metric_id in by_id else None,
            )

        store.run_once(run_id, "audit", f"auto:{metric_id}", _auto)

    for item in decision.escalations:
        note = item.reasons[0].message if item.reasons else item.tier.value

        def _escalate(item=item, note: str = note) -> None:
            log.append(
                actor="system",
                action=AuditAction.ESCALATION,
                run_id=run_id,
                ticker=ticker,
                metric_id=item.review_id,
                original_value=item.value,
                note=note,
            )

        store.run_once(run_id, "audit", f"escalation:{item.review_id}", _escalate)

    return {
        "extraction": result.model_dump(mode="json"),
        "steps_completed": _steps(state, step),
    }


def _verify(state: GraphState, store) -> dict[str, Any]:
    step = Step.VERIFY
    filing = FilingRef.model_validate(state["filing"])
    result = ExtractionResult.model_validate(state["extraction"])
    decision = AutoDecision.model_validate(state["decision"])
    validations = [ValidationResult.model_validate(v) for v in state.get("validations", [])]
    escalated = [e.review_id for e in decision.escalations]
    rows = load_provider("verify_company")(filing, result.metrics, escalated, validations)
    return {
        "rows": [r.model_dump(mode="json") for r in rows],
        "steps_completed": _steps(state, step),
    }


def _report(state: GraphState, store) -> dict[str, Any]:
    step = Step.REPORT
    rows = [AccuracyRow.model_validate(r) for r in state.get("rows", [])]
    report = load_provider("build_report")(rows)
    return {
        "report": report.model_dump(mode="json"),
        "steps_completed": _steps(state, step),
    }


def build_graph(checkpointer: BaseCheckpointSaver | None = None, store=None):
    """Compile the graph. `store` is the idempotency ledger (defaults to the shared one)."""
    ledger = store or get_store()
    g = StateGraph(GraphState)
    g.add_node(Step.FETCH_FILING.value, lambda s: _fetch(s, ledger))
    g.add_node(Step.EXTRACT.value, lambda s: _extract(s, ledger))
    g.add_node(Step.SCORE.value, lambda s: _score(s, ledger))
    g.add_node(Step.VALIDATE.value, lambda s: _validate(s, ledger))
    g.add_node(Step.DECIDE.value, lambda s: _decide(s, ledger))
    g.add_node(Step.REVIEW_GATE.value, lambda s: _review_gate(s, ledger))
    g.add_node(Step.APPLY_DECISIONS.value, lambda s: _apply(s, ledger))
    g.add_node(Step.VERIFY.value, lambda s: _verify(s, ledger))
    g.add_node(Step.REPORT.value, lambda s: _report(s, ledger))
    order = [s.value for s in Step]
    g.add_edge(START, order[0])
    for a, b in zip(order, order[1:], strict=False):
        g.add_edge(a, b)
    return g.compile(checkpointer=checkpointer)

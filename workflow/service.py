"""Implementation of the WorkflowService Protocol from `shared/interfaces.py`.

The dashboard talks to this; it never computes a tier and never edits a number.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from audit.log import get_log
from audit.verify import verify_log
from shared.config import COMPANIES, get_settings
from shared.interfaces import load_provider
from shared.schemas import (
    AccuracyReport,
    AuditAction,
    AuditEntry,
    AuditVerification,
    AutoDecision,
    EscalationItem,
    ExtractedMetric,
    ExtractionResult,
    ReviewDecision,
    ReviewStatus,
    RiskTier,
    RunRequest,
    RunStatus,
    RunSummary,
    Step,
    Thresholds,
    ValidationResult,
)
from workflow.graph import build_graph
from workflow.idempotency import get_store

_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id     TEXT PRIMARY KEY,
    ticker     TEXT NOT NULL,
    status     TEXT NOT NULL,
    error      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL
);
"""


def _utc() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowService:
    """One process, one graph, one SQLite file per concern."""

    def __init__(
        self, runs_db: str | Path | None = None, checkpoints: str | Path | None = None
    ) -> None:
        settings = get_settings()
        self._runs_path = Path(runs_db or settings.data_dir / "runs.db")
        self._runs_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._runs_path), check_same_thread=False)
        self._db.executescript(_RUNS_SCHEMA)
        ckpt = Path(checkpoints or settings.checkpoint_db_path)
        ckpt.parent.mkdir(parents=True, exist_ok=True)
        self._saver = SqliteSaver(sqlite3.connect(str(ckpt), check_same_thread=False))
        self._store = get_store()
        self._graph = build_graph(self._saver, self._store)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _cfg(run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}}

    def _state(self, run_id: str) -> dict[str, Any]:
        snapshot = self._graph.get_state(self._cfg(run_id))
        return dict(snapshot.values or {})

    def _row(self, run_id: str) -> tuple[Any, ...] | None:
        return self._db.execute(
            "SELECT run_id, ticker, status, error, created_at, updated_at FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()

    def _set_status(self, run_id: str, status: RunStatus, error: str | None = None) -> None:
        now = _utc()
        self._db.execute(
            "INSERT INTO runs (run_id, ticker, status, error, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,"
            " error=excluded.error, updated_at=excluded.updated_at",
            (run_id, self._ticker(run_id), status.value, error, now, now),
        )
        self._db.commit()

    def _ticker(self, run_id: str) -> str:
        row = self._db.execute("SELECT ticker FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return row[0] if row else run_id.split("-")[0]

    def _summary(self, run_id: str) -> RunSummary:
        row = self._row(run_id)
        values = self._state(run_id)
        decision = (
            AutoDecision.model_validate(values["decision"]) if values.get("decision") else None
        )
        metrics = values.get("extraction", {}).get("metrics", [])
        answered = {d["review_id"] for d in values.get("decisions", [])}
        escalations = decision.escalations if decision else []
        snapshot = self._graph.get_state(self._cfg(run_id))
        return RunSummary(
            run_id=run_id,
            ticker=row[1] if row else self._ticker(run_id),
            status=RunStatus(row[2]) if row else RunStatus.PENDING,
            current_step=Step(snapshot.next[0]) if snapshot.next else None,
            steps_completed=[Step(s) for s in values.get("steps_completed", [])],
            side_effect_counts=self._store.counts(run_id),
            total_metrics=len(metrics),
            auto_approved=len(decision.auto_approved_ids) if decision else 0,
            escalated=len(escalations),
            pending_reviews=len([e for e in escalations if e.review_id not in answered]),
        )

    # ------------------------------------------------------------ start / read
    def start_runs(self, request: RunRequest) -> list[RunSummary]:
        thresholds = request.thresholds or self.get_thresholds()
        tickers = [t.upper() for t in request.tickers] or [c.ticker for c in COMPANIES]
        out: list[RunSummary] = []
        for ticker in tickers:
            run_id = f"{ticker}-{uuid4().hex[:8]}"
            self._set_status(run_id, RunStatus.RUNNING)
            state = {
                "run_id": run_id,
                "ticker": ticker,
                "fiscal_year": datetime.now(UTC).year,
                "thresholds": thresholds.model_dump(mode="json"),
                "fault": request.fault.model_dump(mode="json") if request.fault else None,
                "steps_completed": [],
            }
            try:
                self._graph.invoke(state, self._cfg(run_id))
                paused = bool(self._graph.get_state(self._cfg(run_id)).next)
                self._set_status(run_id, RunStatus.PAUSED if paused else RunStatus.COMPLETED)
            except Exception as exc:  # noqa: BLE001 - a failed run must still be visible
                self._set_status(run_id, RunStatus.FAILED, str(exc))
            out.append(self._summary(run_id))
        return out

    def list_runs(self) -> list[RunSummary]:
        rows = self._db.execute("SELECT run_id FROM runs ORDER BY created_at").fetchall()
        return [self._summary(r[0]) for r in rows]

    def get_run(self, run_id: str) -> RunSummary:
        if self._row(run_id) is None:
            raise KeyError(f"unknown run {run_id!r}")
        return self._summary(run_id)

    def _metrics_by_id(self, ticker: str | None = None) -> dict[str, ExtractedMetric]:
        out: dict[str, ExtractedMetric] = {}
        for (run_id,) in self._db.execute("SELECT run_id FROM runs ORDER BY created_at"):
            for raw in self._state(run_id).get("extraction", {}).get("metrics", []):
                metric = ExtractedMetric.model_validate(raw)
                if ticker is None or metric.ticker == ticker.upper():
                    out[metric.id] = metric
        return out

    def list_metrics(self, ticker: str | None = None) -> list[ExtractedMetric]:
        return list(self._metrics_by_id(ticker).values())

    def list_validations(self, ticker: str | None = None) -> list[ValidationResult]:
        out: dict[tuple[str, str, str], ValidationResult] = {}
        for (run_id,) in self._db.execute("SELECT run_id FROM runs ORDER BY created_at"):
            for raw in self._state(run_id).get("validations", []):
                v = ValidationResult.model_validate(raw)
                if ticker is None or v.ticker == ticker.upper():
                    out[(v.ticker, v.check.value, v.fiscal_year.__str__())] = v
        return list(out.values())

    def _reviews(self) -> list[tuple[EscalationItem, bool]]:
        out: list[tuple[EscalationItem, bool]] = []
        for (run_id,) in self._db.execute("SELECT run_id FROM runs ORDER BY created_at"):
            values = self._state(run_id)
            if not values.get("decision"):
                continue
            answered = {d["review_id"] for d in values.get("decisions", [])}
            decision = AutoDecision.model_validate(values["decision"])
            for item in decision.escalations:
                out.append((item, item.review_id in answered))
        return out

    def list_reviews(self, status: ReviewStatus | None = None) -> list[EscalationItem]:
        items = []
        for item, done in self._reviews():
            done_status = ReviewStatus.DONE if done else ReviewStatus.PENDING
            item = item.model_copy(update={"status": done_status})
            if status is None or item.status == status:
                items.append(item)
        return items

    def get_review(self, review_id: str) -> EscalationItem:
        for item, done in self._reviews():
            if item.review_id == review_id:
                return item.model_copy(
                    update={"status": ReviewStatus.DONE if done else ReviewStatus.PENDING}
                )
        raise KeyError(f"unknown review {review_id!r}")

    # ------------------------------------------------------------- decisions
    def _run_for(self, review_id: str) -> str:
        for (run_id,) in self._db.execute("SELECT run_id FROM runs ORDER BY created_at DESC"):
            values = self._state(run_id)
            if not values.get("decision"):
                continue
            decision = AutoDecision.model_validate(values["decision"])
            if any(e.review_id == review_id for e in decision.escalations):
                return run_id
        raise KeyError(f"no run owns review {review_id!r}")

    def submit_decision(self, decision: ReviewDecision) -> RunSummary:
        """The guard lives here, not in the UI: a Red value needs a note to be approved."""
        run_id = self._run_for(decision.review_id)
        item = self.get_review(decision.review_id)
        approve = decision.decision.value == "approve"
        if item.tier == RiskTier.RED and approve and not (decision.note or "").strip():
            raise ValueError(
                "This value is Red: approve it only with a note explaining why, or correct it."
            )
        self._graph.invoke(Command(resume=[decision.model_dump(mode="json")]), self._cfg(run_id))
        paused = bool(self._graph.get_state(self._cfg(run_id)).next)
        self._set_status(run_id, RunStatus.PAUSED if paused else RunStatus.COMPLETED)
        return self._summary(run_id)

    # ------------------------------------------------------------ thresholds
    def get_thresholds(self) -> Thresholds:
        row = self._db.execute("SELECT value FROM kv WHERE key='thresholds'").fetchone()
        if row is None:
            return get_settings().default_thresholds()
        return Thresholds.model_validate_json(row[0])

    def set_thresholds(self, thresholds: Thresholds, actor: str) -> Thresholds:
        previous = self.get_thresholds()
        self._db.execute(
            "INSERT INTO kv (key, value) VALUES ('thresholds', ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (thresholds.model_dump_json(),),
        )
        self._db.commit()
        get_log().append(
            actor=actor,
            action=AuditAction.THRESHOLD_CHANGE,
            note=f"confidence {previous.confidence:.2f}->{thresholds.confidence:.2f}, "
            f"critical {previous.confidence_critical:.2f}->{thresholds.confidence_critical:.2f}",
        )
        return thresholds

    # ----------------------------------------------------------------- audit
    def list_audit(self) -> list[AuditEntry]:
        return get_log().entries()

    def verify_audit(self) -> AuditVerification:
        return verify_log(get_log())

    def get_report(self) -> AccuracyReport | None:
        for (run_id,) in self._db.execute("SELECT run_id FROM runs ORDER BY created_at DESC"):
            report = self._state(run_id).get("report")
            if report:
                return AccuracyReport.model_validate(report)
        return None

    def estimate_escalations(self, thresholds: Thresholds) -> int:
        """Dry-run for the sliders: how many values WOULD pause. Writes nothing."""
        decided = load_provider("decide")
        total = 0
        for (run_id,) in self._db.execute("SELECT run_id FROM runs"):
            values = self._state(run_id)
            if not values.get("extraction") or not values.get("validations"):
                continue
            result = ExtractionResult.model_validate(values["extraction"])
            validations = [ValidationResult.model_validate(v) for v in values["validations"]]
            total += len(decided(result, validations, thresholds).escalations)
        return total


_SERVICE: WorkflowService | None = None


def get_service() -> WorkflowService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = WorkflowService()
    return _SERVICE

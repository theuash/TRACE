"""Implementation of the WorkflowService Protocol from `shared/interfaces.py`.

The dashboard talks to this; it never computes a tier and never edits a number.

Storage is PostgreSQL (Neon): runs and thresholds in `runs`/`kv`, the LangGraph checkpoints in
the checkpointer's own tables, side effects in `side_effects`, and the decisions in the
append-only `audit_entries`.
"""

from __future__ import annotations

import atexit
import threading
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg_pool import ConnectionPool

from audit.log import get_log
from audit.verify import verify_log
from db.postgres import Database, get_database
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
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _utc() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowService:
    """One process, one graph, one PostgreSQL database."""

    def __init__(
        self, dsn: str | None = None, checkpoints: str | None = None, *, schema: str = "public"
    ) -> None:
        """`dsn` is a PostgreSQL URL; without one the configured database is used.

        `checkpoints` is accepted for backwards compatibility and ignored: the LangGraph
        checkpoints now live in PostgreSQL as well.
        """
        self._db = Database(dsn, schema=schema) if dsn else get_database()
        # The checkpointer runs DDL (CREATE INDEX CONCURRENTLY) that cannot run inside a
        # transaction, so it gets its own pool in autocommit mode. The Neon pooler refuses
        # `search_path` as a startup parameter, so on a pooled URL the checkpoint tables
        # live in `public`; on a direct URL they follow the requested schema.
        pooled = "-pooler" in self._db.url
        options = "" if pooled or schema == "public" else f"-c search_path={schema}"
        self._ckpt_pool = ConnectionPool(
            conninfo=self._db.url,
            min_size=1,
            max_size=5,
            kwargs={"autocommit": True, "options": options},
            open=True,
        )
        self._saver = PostgresSaver(self._ckpt_pool)
        self._saver.setup()
        self._store = get_store(dsn, schema=schema) if dsn else get_store()
        self._graph = build_graph(self._saver, self._store)
        self._state_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._next_steps: dict[str, list[str]] = {}
        self._state_ttl = 2.0
        atexit.register(self.close)

    def close(self) -> None:
        """Release the checkpointer pool. The shared database pool is closed at exit."""
        try:
            self._ckpt_pool.close()
        except Exception:  # pragma: no cover - best effort at exit
            pass

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _cfg(run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}}

    def _state(self, run_id: str) -> dict[str, Any]:
        snapshot = self._graph.get_state(self._cfg(run_id))
        return dict(snapshot.values or {})

    def _row(self, run_id: str) -> dict[str, Any] | None:
        return self._db.fetch_one(
            "SELECT run_id, ticker, status, error, created_at, updated_at"
            " FROM runs WHERE run_id=%s",
            (run_id,),
        )

    def _set_status(self, run_id: str, status: RunStatus, error: str | None = None) -> None:
        self._invalidate(run_id)
        now = _utc()
        self._db.execute(
            "INSERT INTO runs (run_id, ticker, status, error, created_at, updated_at)"
            " VALUES (%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,"
            " error=excluded.error, updated_at=excluded.updated_at",
            (run_id, self._ticker(run_id), status.value, error, now, now),
        )

    def _ticker(self, run_id: str) -> str:
        row = self._db.fetch_one("SELECT ticker FROM runs WHERE run_id=%s", (run_id,))
        return str(row["ticker"]) if row else run_id.split("-")[0]

    def _run_ids(self, order: str = "created_at") -> list[str]:
        rows = self._db.fetch_all(f"SELECT run_id FROM runs ORDER BY {order}")
        return [str(row["run_id"]) for row in rows]

    def _state(self, run_id: str) -> dict[str, Any]:
        """The graph state of a run, cached for a moment.

        Reading it means reading the LangGraph checkpoint out of PostgreSQL, and every read
        costs a round trip. The dashboard polls every couple of seconds, so a short cache
        keeps the UI responsive without ever showing a stale decision (decisions invalidate it).
        """
        cached = self._state_cache.get(run_id)
        now = time.monotonic()
        if cached is not None and now - cached[0] < self._state_ttl:
            return cached[1]
        snapshot = self._graph.get_state(self._cfg(run_id))
        values = dict(snapshot.values or {})
        self._state_cache[run_id] = (now, values)
        self._next_steps[run_id] = list(snapshot.next or [])
        return values

    def _invalidate(self, run_id: str | None = None) -> None:
        """After a write: the cached state is stale."""
        if run_id is None:
            self._state_cache.clear()
            self._next_steps.clear()
            return
        self._state_cache.pop(run_id, None)
        self._next_steps.pop(run_id, None)

    def _summary(self, run_id: str) -> RunSummary:
        row = self._row(run_id)
        return self._summary_from_row(row, self._store.counts(run_id))

    def _summary_from_row(self, row: dict[str, Any] | None, counts: dict[str, int]) -> RunSummary:
        run_id = str(row["run_id"]) if row else ""
        values = self._state(run_id)
        decision = (
            AutoDecision.model_validate(values["decision"]) if values.get("decision") else None
        )
        metrics = values.get("extraction", {}).get("metrics", [])
        answered = {d["review_id"] for d in values.get("decisions", [])}
        escalations = decision.escalations if decision else []
        next_steps = self._next_steps.get(run_id) or []
        return RunSummary(
            run_id=run_id,
            ticker=str(row["ticker"]) if row else "",
            status=RunStatus(str(row["status"])) if row else RunStatus.PENDING,
            error=str(row["error"]) if row and row.get("error") else None,
            current_step=Step(next_steps[0]) if next_steps else None,
            steps_completed=[Step(s) for s in values.get("steps_completed", [])],
            side_effect_counts=counts,
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
        """Every run, in one query for the rows and one for the side-effect counts.

        Each round trip to the database costs about a second through the Neon pooler, so the
        dashboard's polling must not turn into a query per run.
        """
        rows = self._db.fetch_all(
            "SELECT run_id, ticker, status, error, created_at, updated_at"
            " FROM runs ORDER BY created_at"
        )
        counts: dict[str, dict[str, int]] = {}
        for row in self._db.fetch_all(
            "SELECT run_id, step, count(*) AS n FROM side_effects GROUP BY run_id, step"
        ):
            counts.setdefault(str(row["run_id"]), {})[str(row["step"])] = int(row["n"])
        return [self._summary_from_row(row, counts.get(str(row["run_id"]), {})) for row in rows]

    def get_run(self, run_id: str) -> RunSummary:
        if self._row(run_id) is None:
            raise KeyError(f"unknown run {run_id!r}")
        return self._summary(run_id)

    def _metrics_by_id(self, ticker: str | None = None) -> dict[str, ExtractedMetric]:
        out: dict[str, ExtractedMetric] = {}
        for run_id in self._run_ids():
            for raw in self._state(run_id).get("extraction", {}).get("metrics", []):
                metric = ExtractedMetric.model_validate(raw)
                if ticker is None or metric.ticker == ticker.upper():
                    out[metric.id] = metric
        return out

    def list_metrics(self, ticker: str | None = None) -> list[ExtractedMetric]:
        return list(self._metrics_by_id(ticker).values())

    def list_validations(self, ticker: str | None = None) -> list[ValidationResult]:
        out: dict[tuple[str, str, str], ValidationResult] = {}
        for run_id in self._run_ids():
            for raw in self._state(run_id).get("validations", []):
                v = ValidationResult.model_validate(raw)
                if ticker is None or v.ticker == ticker.upper():
                    out[(v.ticker, v.check.value, v.fiscal_year.__str__())] = v
        return list(out.values())

    def _reviews(self) -> list[tuple[EscalationItem, bool]]:
        out: list[tuple[EscalationItem, bool]] = []
        for run_id in self._run_ids():
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
        for run_id in self._run_ids("created_at DESC"):
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
        try:
            self._graph.invoke(
                Command(resume=[decision.model_dump(mode="json")]), self._cfg(run_id)
            )
        except Exception as exc:  # noqa: BLE001 - a failed resume must be visible, not silent
            self._set_status(run_id, RunStatus.FAILED, f"{type(exc).__name__}: {exc}")
            raise
        paused = bool(self._graph.get_state(self._cfg(run_id)).next)
        self._set_status(run_id, RunStatus.PAUSED if paused else RunStatus.COMPLETED)
        return self._summary(run_id)

    # ------------------------------------------------------------ thresholds
    def get_thresholds(self) -> Thresholds:
        row = self._db.fetch_one("SELECT value FROM kv WHERE key='thresholds'")
        if row is None:
            return get_settings().default_thresholds()
        return Thresholds.model_validate_json(str(row["value"]))

    def set_thresholds(self, thresholds: Thresholds, actor: str) -> Thresholds:
        previous = self.get_thresholds()
        self._db.execute(
            "INSERT INTO kv (key, value, updated_at) VALUES ('thresholds', %s, now())"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (thresholds.model_dump_json(),),
        )
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

    def read_audit(self) -> tuple[list[AuditEntry], list[int]]:
        """Readable decisions plus the seq numbers of rows that could not be parsed."""
        return get_log().read_entries()

    def verify_audit(self) -> AuditVerification:
        return verify_log(get_log())

    def get_timeline(self, run_id: str) -> list[dict]:
        """One event per completed step, plus every audit row for this run. Read-only."""
        if self._row(run_id) is None:
            raise KeyError(f"unknown run {run_id!r}")
        values = self._state(run_id)
        row = self._row(run_id) or {}
        events: list[dict] = [
            {
                "at": str(row.get("created_at") or ""),
                "kind": "step",
                "name": step,
                "detail": "",
                "actor": "system",
            }
            for step in values.get("steps_completed", [])
        ]
        for entry in self.list_audit():
            if entry.run_id != run_id:
                continue
            events.append(
                {
                    "at": entry.timestamp.isoformat(),
                    "kind": entry.action.value,
                    "name": entry.metric_id or "",
                    "detail": entry.note or "",
                    "actor": entry.actor,
                }
            )
        events.sort(key=lambda event: event["at"])
        return events

    def get_report(self) -> AccuracyReport | None:
        for run_id in self._run_ids("created_at DESC"):
            report = self._state(run_id).get("report")
            if report:
                return AccuracyReport.model_validate(report)
        return None

    def estimate_escalations(self, thresholds: Thresholds) -> int:
        """Dry-run for the sliders: how many values WOULD pause. Writes nothing."""
        decided = load_provider("decide")
        total = 0
        for run_id in self._run_ids():
            values = self._state(run_id)
            if not values.get("extraction") or not values.get("validations"):
                continue
            result = ExtractionResult.model_validate(values["extraction"])
            validations = [ValidationResult.model_validate(v) for v in values["validations"]]
            total += len(decided(result, validations, thresholds).escalations)
        return total


_SERVICE: WorkflowService | None = None
_SERVICE_LOCK = threading.Lock()


def get_service() -> WorkflowService:
    """One service per process. The lock matters: creating it runs the checkpointer's DDL, and
    two concurrent requests doing that at once block each other for minutes on a cold database."""
    global _SERVICE
    if _SERVICE is None:
        with _SERVICE_LOCK:
            if _SERVICE is None:
                _SERVICE = WorkflowService()
    return _SERVICE

"""The function contracts between the three people. FROZEN after kickoff.

Each person implements the functions they own at EXACTLY the module path and name listed in
`PROVIDERS`. Nobody imports another person's module directly: everything goes through
`load_provider(name)`, so a missing or unfinished module can be swapped for a fake.

Who owns what
-------------
Person 1: fetch_filing, extract_filing, score_extraction, explain_anomaly, (llm.client)
Person 2: run_validations, decide, workflow_service, and the fakes in workflow/fakes.py
Person 3: verify_company, build_report, mock_service, and the API app
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, Protocol

from shared.schemas import (
    AccuracyReport,
    AccuracyRow,
    AuditEntry,
    AuditVerification,
    AutoDecision,
    Company,
    EscalationItem,
    ExtractedMetric,
    ExtractionResult,
    FilingRef,
    ReviewDecision,
    ReviewStatus,
    RunRequest,
    RunSummary,
    Thresholds,
    ValidationResult,
)

# ----------------------------------------------------------- function-level contracts
# (signatures documented here as Protocols; implementations are plain module functions)


class FetchFiling(Protocol):
    """Person 1. Download (or load from cache) the latest 10-K. Must be cache-first."""

    def __call__(self, company: Company) -> FilingRef: ...


class ExtractFiling(Protocol):
    """Person 1. Parse the 10-K document into metrics + evidence. NEVER reads Company Facts."""

    def __call__(self, filing: FilingRef) -> ExtractionResult: ...


class ScoreExtraction(Protocol):
    """Person 1. Fill `confidence` and `confidence_signals` on every metric from extraction-time
    signals only (extractor agreement, label match quality, unit/period clarity)."""

    def __call__(self, result: ExtractionResult) -> ExtractionResult: ...


class ExplainAnomaly(Protocol):
    """Person 1. One or two plain-English sentences explaining a failed check. Must not raise:
    return a deterministic fallback string if the LLM is unavailable."""

    def __call__(self, validation: ValidationResult, metric: ExtractedMetric | None) -> str: ...


class RunValidations(Protocol):
    """Person 2. Accounting equation, segment sum, year-on-year. Returns passed AND failed."""

    def __call__(self, result: ExtractionResult, thresholds: Thresholds) -> list[ValidationResult]: ...


class Decide(Protocol):
    """Person 2. Auto-approve or escalate every current-year metric, with plain-English reasons.
    A failed validation escalates every metric listed in `ValidationResult.metric_ids`."""

    def __call__(
        self,
        result: ExtractionResult,
        validations: list[ValidationResult],
        thresholds: Thresholds,
    ) -> AutoDecision: ...


class VerifyCompany(Protocol):
    """Person 3. Compare against XBRL Company Facts (the ONLY place allowed to call it)."""

    def __call__(
        self,
        filing: FilingRef,
        final_metrics: list[ExtractedMetric],
        escalated_ids: list[str],
        validations: list[ValidationResult],
    ) -> list[AccuracyRow]: ...


class BuildReport(Protocol):
    """Person 3. Aggregate rows from all companies into the report, incl. calibration buckets."""

    def __call__(self, rows: list[AccuracyRow]) -> AccuracyReport: ...


# ------------------------------------------------------------------ workflow service


class WorkflowService(Protocol):
    """Person 2 implements this in workflow/service.py. Person 3 wraps it in the FastAPI app
    and also ships api/mock_service.py implementing the same Protocol with fixture data."""

    def start_runs(self, request: RunRequest) -> list[RunSummary]: ...
    def list_runs(self) -> list[RunSummary]: ...
    def get_run(self, run_id: str) -> RunSummary: ...
    def list_metrics(self, ticker: str | None = None) -> list[ExtractedMetric]: ...
    def list_validations(self, ticker: str | None = None) -> list[ValidationResult]: ...
    def list_reviews(self, status: ReviewStatus | None = None) -> list[EscalationItem]: ...
    def get_review(self, review_id: str) -> EscalationItem: ...
    def submit_decision(self, decision: ReviewDecision) -> RunSummary: ...
    def get_thresholds(self) -> Thresholds: ...
    def set_thresholds(self, thresholds: Thresholds, actor: str) -> Thresholds: ...
    def list_audit(self) -> list[AuditEntry]: ...
    def verify_audit(self) -> AuditVerification: ...
    def get_report(self) -> AccuracyReport | None: ...
    def estimate_escalations(self, thresholds: Thresholds) -> int:
        """Dry-run: how many metrics WOULD escalate at these thresholds (for the sliders)."""
        ...


# ----------------------------------------------------------------- provider registry

PROVIDERS: dict[str, str] = {
    # Person 1
    "fetch_filing": "extraction.pipeline:fetch_filing",
    "extract_filing": "extraction.pipeline:extract_filing",
    "score_extraction": "extraction.confidence:score_extraction",
    "explain_anomaly": "llm.explain:explain_anomaly",
    # Person 2
    "run_validations": "validation.engine:run_validations",
    "decide": "validation.decide:decide",
    "workflow_service": "workflow.service:get_service",
    # Person 3
    "verify_company": "verification.ground_truth:verify_company",
    "build_report": "verification.report:build_report",
    "mock_service": "api.mock_service:get_service",
}

# Person 2's stand-ins so the graph runs before Person 1 / Person 3 finish. Used when USE_FAKES=true.
FAKES: dict[str, str] = {
    "fetch_filing": "workflow.fakes:fetch_filing",
    "extract_filing": "workflow.fakes:extract_filing",
    "score_extraction": "workflow.fakes:score_extraction",
    "explain_anomaly": "workflow.fakes:explain_anomaly",
    "verify_company": "workflow.fakes:verify_company",
    "build_report": "workflow.fakes:build_report",
}


def load_provider(name: str, *, use_fakes: bool | None = None) -> Callable[..., Any]:
    """Resolve a contract function by name. The only sanctioned way to call a teammate's code."""
    if use_fakes is None:
        from shared.config import get_settings

        use_fakes = get_settings().use_fakes
    table = FAKES if (use_fakes and name in FAKES) else PROVIDERS
    if name not in table:
        raise KeyError(f"Unknown provider {name!r}. Known: {sorted(PROVIDERS)}")
    module_path, func_name = table[name].split(":")
    return getattr(importlib.import_module(module_path), func_name)


__all__ = [
    "FAKES",
    "PROVIDERS",
    "BuildReport",
    "Decide",
    "ExplainAnomaly",
    "ExtractFiling",
    "FetchFiling",
    "RunValidations",
    "ScoreExtraction",
    "VerifyCompany",
    "WorkflowService",
    "load_provider",
]

"""Shared data contracts for the whole team.

FROZEN after kickoff. Nobody edits this file alone. If you need a change, create
`docs/requests/<you>-to-all-<topic>.md`, agree as a team, then ship it as a
`contract/...` branch reviewed by all three people.

Conventions
-----------
* Money is `Decimal`, never `float`. `value` is always in FULL units (USD, not millions):
  the "in millions" scale printed in the filing has already been applied.
* Datetimes are timezone-aware UTC.
* `extra="forbid"` everywhere: a misspelled field fails loudly instead of silently.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# --------------------------------------------------------------------------- enums


class Metric(StrEnum):
    REVENUE = "revenue"
    NET_INCOME = "net_income"
    TOTAL_ASSETS = "total_assets"
    TOTAL_LIABILITIES = "total_liabilities"
    SHAREHOLDERS_EQUITY = "shareholders_equity"
    OPERATING_CASH_FLOW = "operating_cash_flow"
    OPERATING_INCOME = "operating_income"
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"
    GROSS_PROFIT = "gross_profit"  # optional: not every company reports it
    DILUTED_EPS = "diluted_eps"  # optional: unit is USD per share


# The six metrics the problem statement makes mandatory.
REQUIRED_METRICS: tuple[Metric, ...] = (
    Metric.REVENUE,
    Metric.NET_INCOME,
    Metric.TOTAL_ASSETS,
    Metric.TOTAL_LIABILITIES,
    Metric.SHAREHOLDERS_EQUITY,
    Metric.OPERATING_CASH_FLOW,
)
# Our guaranteed 8 per filing.
CORE_METRICS: tuple[Metric, ...] = REQUIRED_METRICS + (
    Metric.OPERATING_INCOME,
    Metric.CASH_AND_EQUIVALENTS,
)
OPTIONAL_METRICS: tuple[Metric, ...] = (Metric.GROSS_PROFIT, Metric.DILUTED_EPS)


class Unit(StrEnum):
    USD = "USD"
    USD_PER_SHARE = "USD/share"


METRIC_UNITS: dict[Metric, Unit] = {Metric.DILUTED_EPS: Unit.USD_PER_SHARE}


class Extractor(StrEnum):
    TABLE = "table"  # deterministic HTML table parser
    LLM = "llm"  # LLM fallback
    BOTH = "both"  # both ran and agreed
    DERIVED = "derived"  # computed from components (e.g. Amazon has no "Total liabilities" line)


class MetricStatus(StrEnum):
    EXTRACTED = "extracted"  # just extracted, no decision yet
    AUTO_APPROVED = "auto_approved"
    FLAGGED = "flagged"  # waiting for a human
    APPROVED = "approved"  # human approved
    CORRECTED = "corrected"  # human edited the value
    REJECTED = "rejected"  # human rejected: value is not usable


class DecisionType(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"


class CheckName(StrEnum):
    ACCOUNTING_EQUATION = "accounting_equation"
    SEGMENT_SUM = "segment_sum"
    YOY_CHANGE = "yoy_change"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class RiskTier(StrEnum):
    """Traffic light. Computed by validation.decide from confidence AND validation results."""

    GREEN = "green"  # auto-approved: confident and arithmetically clean
    YELLOW = "yellow"  # pauses: medium confidence, or only warning-severity failures
    RED = "red"  # pauses and blocks the report: hard failure or very low confidence


class EscalationKind(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    VALIDATION_FAILED = "validation_failed"
    EXTRACTOR_DISAGREEMENT = "extractor_disagreement"
    MISSING_VALUE = "missing_value"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"  # waiting for a human review
    COMPLETED = "completed"
    FAILED = "failed"


class Step(StrEnum):
    """Graph steps in order. Used for checkpoints and the visible 'nothing repeated' counters."""

    FETCH_FILING = "fetch_filing"
    EXTRACT = "extract"
    SCORE = "score"
    VALIDATE = "validate"
    DECIDE = "decide"
    REVIEW_GATE = "review_gate"
    APPLY_DECISIONS = "apply_decisions"
    VERIFY = "verify"
    REPORT = "report"


class AuditAction(StrEnum):
    HUMAN_DECISION = "human_decision"
    AUTO_APPROVAL = "auto_approval"
    ESCALATION = "escalation"
    THRESHOLD_CHANGE = "threshold_change"


# ---------------------------------------------------------------- company / filing


class Company(Base):
    ticker: str
    name: str
    cik: str  # 10 digits, zero padded, e.g. "0000320193"

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("cik")
    @classmethod
    def _cik(cls, v: str) -> str:
        digits = v.strip()
        if not digits.isdigit() or len(digits) > 10:
            raise ValueError("cik must be up to 10 digits")
        return digits.zfill(10)


class FilingRef(Base):
    company: Company
    accession_number: str  # e.g. "0000320193-24-000123"
    filing_date: date
    fiscal_year: int
    period_end: date
    primary_document: str  # file name of the main 10-K HTML
    url: str
    local_path: str | None = None  # cached copy under data/


# ------------------------------------------------------------------------ extraction


class SourceEvidence(Base):
    snippet: str  # surrounding text/row from the filing, shown to the reviewer
    matched_text: str  # the exact substring inside `snippet` to highlight, e.g. "352,583"
    location: str  # human readable, e.g. "Consolidated Balance Sheets, row 'Total assets'"
    table_index: int | None = None
    row_label: str | None = None
    source_url: str | None = None


def make_metric_id(ticker: str, metric: Metric | str, fiscal_year: int) -> str:
    """Deterministic id. Also used as review_id and as the idempotency key for side effects."""
    return f"{ticker.upper()}:{Metric(metric).value}:{fiscal_year}"


class ExtractedMetric(Base):
    ticker: str
    metric: Metric
    fiscal_year: int
    period_end: date
    period_start: date | None = None  # for flow metrics (revenue, net income, cash flow)
    value: Decimal  # FULL units (scale applied)
    unit: Unit = Unit.USD
    scale: int = 1  # scale printed in the filing: 1, 1_000 or 1_000_000 (informational)
    raw_text: str  # exactly as printed, e.g. "352,583"
    extractor: Extractor
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_signals: dict[str, float] = Field(default_factory=dict)
    evidence: SourceEvidence
    status: MetricStatus = MetricStatus.EXTRACTED
    reviewed_value: Decimal | None = None  # set only by a human EDIT decision

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @property
    def id(self) -> str:
        return make_metric_id(self.ticker, self.metric, self.fiscal_year)

    @property
    def effective_value(self) -> Decimal | None:
        """The value the system stands behind. None if not yet decided or rejected."""
        if self.status == MetricStatus.CORRECTED:
            return self.reviewed_value
        if self.status in (MetricStatus.AUTO_APPROVED, MetricStatus.APPROVED):
            return self.value
        return None


class SegmentValue(Base):
    name: str
    value: Decimal


class SegmentTable(Base):
    """Segment breakdown found in the filing, used by the segment-sum validation."""

    ticker: str
    fiscal_year: int
    total_metric: Metric  # which total the segments should add up to (usually REVENUE)
    segments: list[SegmentValue]
    reported_total: Decimal
    evidence: SourceEvidence


class ExtractionResult(Base):
    filing: FilingRef
    metrics: list[ExtractedMetric]  # current fiscal year: these get reviewed
    prior_metrics: list[ExtractedMetric] = Field(default_factory=list)  # prior year, for YoY only
    segments: list[SegmentTable] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def current(self, metric: Metric) -> ExtractedMetric | None:
        return next((m for m in self.metrics if m.metric == metric), None)

    def prior(self, metric: Metric) -> ExtractedMetric | None:
        return next((m for m in self.prior_metrics if m.metric == metric), None)


# ------------------------------------------------------------ thresholds / validation


class Thresholds(Base):
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)  # green boundary
    confidence_critical: float = Field(default=0.60, ge=0.0, le=1.0)  # red boundary
    yoy_change_pct: float = Field(default=40.0, gt=0)
    accounting_tolerance_pct: float = Field(default=0.1, ge=0)
    segment_tolerance_pct: float = Field(default=0.1, ge=0)
    per_metric_confidence: dict[Metric, float] = Field(default_factory=dict)  # adaptive overrides

    @model_validator(mode="after")
    def _critical_below_green(self) -> Thresholds:
        if self.confidence_critical > self.confidence:
            raise ValueError("confidence_critical must be <= confidence")
        return self

    def confidence_for(self, metric: Metric) -> float:
        return self.per_metric_confidence.get(metric, self.confidence)

    def is_low_confidence(self, metric: Metric, confidence: float) -> bool:
        return confidence < self.confidence_for(metric)


class ValidationResult(Base):
    ticker: str
    fiscal_year: int
    check: CheckName
    passed: bool
    severity: Severity = Severity.INFO
    detail: str  # plain English: "Assets (352.6B) != Liabilities (290.4B) + Equity (62.1B); off by 0.4%"
    metric_ids: list[str] = Field(default_factory=list)  # metrics involved, all escalate if failed
    expected: Decimal | None = None
    actual: Decimal | None = None
    difference_pct: float | None = None
    explanation: str | None = None  # optional LLM explanation for anomalies


class EscalationReason(Base):
    kind: EscalationKind
    message: str  # plain English, shown to the reviewer


class EscalationItem(Base):
    """What the reviewer sees. review_id == ExtractedMetric.id."""

    review_id: str
    ticker: str
    metric: Metric
    fiscal_year: int
    value: Decimal
    unit: Unit = Unit.USD
    confidence: float
    tier: RiskTier = RiskTier.YELLOW  # set by decide(); the UI only renders it
    reasons: list[EscalationReason]
    evidence: SourceEvidence
    failed_checks: list[ValidationResult] = Field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = Field(default_factory=utcnow)


class AutoDecision(Base):
    """Output of validation.decide.decide()."""

    auto_approved_ids: list[str]
    escalations: list[EscalationItem]


# ------------------------------------------------------------------- human review


class ReviewDecision(Base):
    review_id: str
    decision: DecisionType
    corrected_value: Decimal | None = None
    reviewer: str
    note: str | None = None
    decided_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _edit_needs_value(self) -> ReviewDecision:
        if self.decision == DecisionType.EDIT and self.corrected_value is None:
            raise ValueError("decision 'edit' requires corrected_value")
        return self


# ------------------------------------------------------------------------ audit log

GENESIS_HASH = "0" * 64


class AuditEntry(Base):
    """One row of the append-only, hash-chained audit log.

    Hash rule (the single source of truth, used by the writer AND the verifier):
        hash = sha256(prev_hash + canonical_json(all fields except `hash`))
    Store Decimals and datetimes exactly as `model_dump(mode="json")` produces them.
    """

    seq: int = Field(ge=1)
    timestamp: datetime = Field(default_factory=utcnow)
    actor: str  # reviewer name, or "system"
    action: AuditAction
    run_id: str | None = None
    ticker: str | None = None
    metric_id: str | None = None
    original_value: Decimal | None = None
    corrected_value: Decimal | None = None
    decision: DecisionType | None = None
    note: str | None = None
    prev_hash: str = GENESIS_HASH
    hash: str = ""

    def canonical_payload(self) -> str:
        data = self.model_dump(mode="json", exclude={"hash"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def compute_hash(self) -> str:
        return hashlib.sha256((self.prev_hash + self.canonical_payload()).encode()).hexdigest()

    def seal(self) -> AuditEntry:
        return self.model_copy(update={"hash": self.compute_hash()})


class AuditVerification(Base):
    ok: bool
    entries_checked: int
    first_broken_seq: int | None = None
    message: str


# ------------------------------------------------------------- verification / report


class AccuracyRow(Base):
    metric_id: str
    ticker: str
    metric: Metric
    fiscal_year: int
    extracted_value: Decimal
    final_value: Decimal | None  # after human review; None if rejected / undecided
    truth_value: Decimal | None  # XBRL; None if XBRL has no matching fact
    xbrl_tag: str | None = None
    extraction_correct: bool | None = None  # extracted vs truth; None if no truth
    final_correct: bool | None = None
    confidence: float
    escalated: bool
    escalation_justified: bool | None = None  # escalated AND (extraction wrong OR check failed)
    note: str | None = None


class CalibrationBucket(Base):
    lower: float
    upper: float
    count: int
    accuracy: float | None  # None if the bucket is empty


class AccuracyReport(Base):
    generated_at: datetime = Field(default_factory=utcnow)
    rows: list[AccuracyRow]
    total_values: int
    compared_values: int  # values that had XBRL truth
    overall_extraction_accuracy: float | None
    final_accuracy: float | None  # after human review
    auto_approved_count: int
    escalated_count: int
    escalation_precision: float | None  # share of escalations that were genuine problems
    by_metric: dict[str, float] = Field(default_factory=dict)
    by_company: dict[str, float] = Field(default_factory=dict)
    calibration: list[CalibrationBucket] = Field(default_factory=list)
    missing_truth: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ runs / API shapes


class FaultSpec(Base):
    """Demo fault injection: corrupt one extracted value before validation runs."""

    ticker: str
    metric: Metric = Metric.TOTAL_ASSETS
    delta_pct: float = 3.0


class RunRequest(Base):
    tickers: list[str] = Field(default_factory=list)  # empty = all configured companies
    fault: FaultSpec | None = None
    thresholds: Thresholds | None = None


class RunSummary(Base):
    run_id: str  # also the LangGraph thread_id: one per company
    ticker: str
    status: RunStatus
    current_step: Step | None = None
    steps_completed: list[Step] = Field(default_factory=list)
    # How many times each side effect really ran, e.g. {"fetch_filing": 1}.
    # Shown in the dashboard to PROVE nothing repeated after a resume. Every value must stay 1.
    side_effect_counts: dict[str, int] = Field(default_factory=dict)
    total_metrics: int = 0
    auto_approved: int = 0
    escalated: int = 0
    pending_reviews: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

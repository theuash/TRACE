/** Audit lifecycle statuses used across the TRACE contract. */
export const AUDIT_STATUSES = [
  "STARTED",
  "FETCHED",
  "EXTRACTED",
  "VALIDATED",
  "PAUSED_FOR_REVIEW",
  "HUMAN_REVIEWED",
  "AUTO_APPROVED",
  "COMPLETED",
  "FAILED",
] as const;

export type AuditStatusValue = (typeof AUDIT_STATUSES)[number];

export type DecisionState =
  | "FLAGGED"
  | "PENDING"
  | "AUTO_APPROVED"
  | "APPROVED"
  | "CORRECTED"
  | "REJECTED";

export type EscalationType = "EXTRACTION_RISK" | "FINANCIAL_ANOMALY";

export type Severity = "HIGH" | "MEDIUM" | "LOW";

export type ValidationStatus = "PASSED" | "FAILED" | "SKIPPED";

export type ConfidenceLabel = "HIGH" | "LOW";

export type ReviewDecisionValue = "AUTO_APPROVED" | "APPROVED" | "CORRECTED" | "REJECTED";

export interface ConfidenceSignals {
  snippet_grounding: number | null;
  concept_match: number | null;
  unit_consistency: number | null;
  period_consistency: number | null;
  prior_year_sanity: number | null;
  extractor_agreement: number | null;
  column_period: number | null;
  cross_statement: number | null;
  llm_confidence: number | null;
}

export interface Metric {
  metric_name: string;
  value_usd: number;
  original_value: number;
  unit: string;
  period: string;
  prior_year_value_usd: number | null;
  confidence: number;
  confidence_label: ConfidenceLabel;
  confidence_signals: ConfidenceSignals;
  source_snippet: string;
  /** The exact substring inside source_snippet to highlight. */
  matched_text?: string;
  source_header: string;
  source_row: string;
  /** The SEC document this value was read from. */
  source_url?: string;
  decision_state: DecisionState;
}

export interface FlaggedItem extends Metric {
  /** Stable per-metric identity from the API. List rows and decisions key on this, never on
   * metric_name: the same metric can legitimately produce more than one escalation. */
  review_id?: string;
  /** Server-computed risk tier. The UI only renders it, never recomputes it. */
  tier?: "red" | "yellow" | "green";
  reasons: string[];
  rules: string[];
  severity: Severity;
  escalation_types: EscalationType[];
  /** What the human decided, read from the audit log. */
  decided_at?: string | null;
  reviewer?: string | null;
  reviewer_note?: string | null;
  audit_seq?: number | null;
  corrected_value?: number | null;
}

export interface ValidationCheck {
  rule_name: string;
  metric_name: string;
  status: ValidationStatus;
  reason: string;
  details: string;
  metrics_involved: string[];
}

export interface Thresholds {
  confidence_threshold: number;
  confidence_critical: number;
  yoy_change_pct: number;
  accounting_tolerance_pct: number;
  segment_tolerance_pct: number;
}

export interface CalibrationBucket {
  lower: number;
  upper: number;
  count: number;
  accuracy: number;
}

export interface AccuracyReport {
  accuracy_pct: number;
  original_accuracy_pct: number;
  auto_approval_accuracy_pct: number;
  auto_approved_count: number;
  escalated_count: number;
  escalation_precision_pct: number;
  escalation_precision_by_type: Record<string, number>;
  escalation_recall_pct: number;
  per_metric_accuracy: Record<string, number>;
  by_company: Record<string, number>;
  metric_details: MetricAccuracyDetail[];
  calibration: CalibrationBucket[];
  missing_truth: string[];
}

export interface EscalationEstimate {
  escalations: number;
}

export interface MetricAccuracyDetail {
  /** Company the value belongs to. Missing on older payloads. */
  ticker?: string;
  metric: string;
  extracted: number;
  final: number;
  xbrl: number;
  match: boolean;
  diff_pct: number;
}

export interface AuditLogRow {
  id: string;
  thread_id: string;
  company_name: string;
  metric_name: string;
  decision: ReviewDecisionValue;
  original_value: number;
  corrected_value: number | null;
  reviewer_notes: string;
  timestamp: string;
  prev_hash: string;
  row_hash: string;
  /** What the row was: a human decision, an auto approval, an escalation, a policy change. */
  action?: string;
}

export interface VerifyResult {
  verified: boolean;
  message: string;
  total_rows: number;
  checked_rows: number;
  broken_row_id: string | null;
}

export interface AuditEvent {
  id: string;
  thread_id: string;
  step: number;
  event: string;
  status: AuditStatusValue;
  timestamp: string;
  detail?: string;
}

export interface AnomalyExplanation {
  metric_name: string;
  title: string;
  detail: string;
  severity: Severity;
}

export interface CompanyInfo {
  name: string;
  ticker: string;
  cik: string;
  industry: string;
  /** True for the five companies the demo ships with; absent on the plain `/companies` list. */
  configured?: boolean;
}

export interface ThreadSummary {
  thread_id: string;
  company_name: string;
  ticker: string;
  cik: string;
  fiscal_year: number | null;
  status: AuditStatusValue;
  flagged_count: number;
  auto_approved_count: number;
  created_at: string;
  updated_at: string;
  accuracy_pct?: number;
  original_accuracy_pct?: number;
  auto_approval_accuracy_pct?: number;
  escalation_precision_pct?: number;
  escalation_recall_pct?: number;
  escalation_precision_by_type?: Record<string, number>;
  metric_details?: MetricAccuracyDetail[];
}

export interface AuditStatus {
  thread_id: string;
  company_name: string;
  ticker: string;
  cik: string;
  fiscal_year: number;
  period_end: string;
  filing_url: string;
  status: AuditStatusValue;
  metrics: Metric[];
  validation_checks: ValidationCheck[];
  flagged_items: FlaggedItem[];
  anomaly_explanations: Record<string, AnomalyExplanation>;
  accuracy_report: AccuracyReport | null;
  thresholds: Thresholds;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: "ok" | "healthy" | "degraded";
  version: string;
  /** "real" = real workflow + XBRL verification, "mock" = fixture data. */
  mode?: "mock" | "real";
  database?: DatabaseStatus;
}

/** What the store behind the app looks like right now. */
export interface DatabaseStatus {
  backend: "postgresql" | "none" | string;
  host: string;
  ok: boolean;
  latency_ms: number | null;
  error: string | null;
}

export interface DatabaseInfo extends DatabaseStatus {
  pooled: boolean;
  tables: Record<string, number>;
  last_audit_write: string | null;
  last_run_write: string | null;
}

export interface StartAuditRequest {
  cik: string;
  confidence_threshold: number;
  yoy_threshold_pct: number;
}

export interface ReviewDecisionInput {
  metric_name: string;
  decision: "APPROVED" | "CORRECTED" | "REJECTED";
  corrected_value?: number;
  reviewer_notes?: string;
}

export interface ResumePayload {
  decisions: ReviewDecisionInput[];
}

export interface AuditLogFilters {
  thread_id?: string;
  company_name?: string;
  decision?: string;
}

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
  source_header: string;
  source_row: string;
  decision_state: DecisionState;
}

export interface FlaggedItem extends Metric {
  reasons: string[];
  rules: string[];
  severity: Severity;
  escalation_types: EscalationType[];
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
  yoy_change_pct: number;
  accounting_tolerance_pct: number;
  segment_tolerance_pct: number;
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
  metric_details: MetricAccuracyDetail[];
}

export interface MetricAccuracyDetail {
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
  demo_only: boolean;
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
  demo_only: boolean;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: "ok" | "healthy" | "degraded";
  version: string;
}

export interface StartAuditRequest {
  cik: string;
  confidence_threshold: number;
  yoy_threshold_pct: number;
  demo_only: boolean;
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

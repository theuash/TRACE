import type {
  AccuracyReport,
  AuditEvent,
  AuditLogFilters,
  AuditLogRow,
  AuditStatus,
  CompanyInfo,
  HealthResponse,
  ResumePayload,
  StartAuditRequest,
  ThreadSummary,
  VerifyResult,
} from "../types";
import { computeRowHash, GENESIS_HASH, verifyChain } from "./hash";
import { FIXTURES, buildAnomalyExplanation, findCompanyByCik, flaggedForCompany, trueValueFor } from "./fixtures";

const THREADS_KEY = "trace.mock.threads.v1";
const LOGS_KEY = "trace.mock.logs.v1";

interface StoredThread extends AuditStatus {
  step_index: number;
  timeline: AuditEvent[];
}

interface MockDatabase {
  threads: Record<string, StoredThread>;
  auditLogs: AuditLogRow[];
}

function makeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36).toUpperCase()}${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
}

function makeEvent(
  threadId: string,
  step: number,
  event: string,
  status: AuditStatus["status"],
  timestamp: string,
  detail?: string
): AuditEvent {
  return { id: makeId("EV"), thread_id: threadId, step, event, status, timestamp, detail };
}

function toStatus(thread: StoredThread): AuditStatus {
  const { step_index: _step, timeline: _timeline, ...status } = thread;
  return status;
}

function ratio(matches: boolean[]): number {
  if (matches.length === 0) return 0;
  return (matches.filter(Boolean).length / matches.length) * 100;
}

export class MockTraceApi {
  private db: MockDatabase;
  private failureMode = false;

  constructor() {
    this.db = this.load();
  }

  private load(): MockDatabase {
    try {
      const rawThreads = window.localStorage.getItem(THREADS_KEY);
      const rawLogs = window.localStorage.getItem(LOGS_KEY);
      const threads: Record<string, StoredThread> = rawThreads ? JSON.parse(rawThreads) : {};
      const auditLogs: AuditLogRow[] = rawLogs ? JSON.parse(rawLogs) : [];
      return { threads, auditLogs };
    } catch {
      return { threads: {}, auditLogs: [] };
    }
  }

  private save() {
    try {
      window.localStorage.setItem(THREADS_KEY, JSON.stringify(this.db.threads));
      window.localStorage.setItem(LOGS_KEY, JSON.stringify(this.db.auditLogs));
    } catch {
      // storage unavailable â€” keep in-memory state
    }
  }

  private delay(min = 300, spread = 550): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, min + Math.random() * spread));
  }

  async health(): Promise<HealthResponse> {
    await this.delay(200, 300);
    return { status: "ok", version: "0.1.0-mock" };
  }

  async listCompanies(): Promise<CompanyInfo[]> {
    await this.delay(250, 400);
    return FIXTURES.companies.map((c) => ({ name: c.name, ticker: c.ticker, cik: c.cik, industry: c.industry }));
  }

  async startAudit(request: StartAuditRequest): Promise<AuditStatus> {
    await this.delay(350, 550);
    const company = findCompanyByCik(request.cik);
    const now = new Date().toISOString();

    if (this.failureMode) {
      const failedId = makeId("TR");
      const thread: StoredThread = {
        thread_id: failedId,
        company_name: company.name,
        ticker: company.ticker,
        cik: company.cik,
        fiscal_year: company.fiscal_year,
        period_end: company.period_end,
        filing_url: company.filing_url,
        status: "FAILED",
        metrics: [],
        validation_checks: [],
        flagged_items: [],
        anomaly_explanations: {},
        accuracy_report: null,
        thresholds: {
          confidence_threshold: request.confidence_threshold,
          yoy_change_pct: request.yoy_threshold_pct,
          accounting_tolerance_pct: 0.001,
          segment_tolerance_pct: 0.001,
        },
        demo_only: request.demo_only,
        created_at: now,
        updated_at: now,
        step_index: 2,
        timeline: [makeEvent(failedId, 2, "Extraction failed", "FAILED", now, "Mock extraction failure (simulate failure enabled)")],
      };
      this.db.threads[failedId] = thread;
      this.save();
      return toStatus(thread);
    }

    const threadId = makeId("TR");
    const thread: StoredThread = {
      thread_id: threadId,
      company_name: company.name,
      ticker: company.ticker,
      cik: company.cik,
      fiscal_year: company.fiscal_year,
      period_end: company.period_end,
      filing_url: company.filing_url,
      status: "STARTED",
      metrics: company.metrics.map((m) => ({ ...m })),
      validation_checks: [],
      flagged_items: [],
      anomaly_explanations: {},
      accuracy_report: null,
      thresholds: {
        confidence_threshold: request.confidence_threshold,
        yoy_change_pct: request.yoy_threshold_pct,
        accounting_tolerance_pct: 0.001,
        segment_tolerance_pct: 0.001,
      },
      demo_only: request.demo_only,
      created_at: now,
      updated_at: now,
      step_index: 0,
      timeline: [makeEvent(threadId, 0, "Thread created", "STARTED", now)],
    };
    this.db.threads[threadId] = thread;
    this.save();
    void this.runPipeline(threadId);
    return toStatus(thread);
  }

  private async runPipeline(threadId: string): Promise<void> {
    const thread = this.db.threads[threadId];
    if (!thread) return;
    const company = findCompanyByCik(thread.cik);
    const flagged = flaggedForCompany(thread.cik);
    const willPause = thread.demo_only || flagged.length > 0;
    const now = () => new Date().toISOString();

    const setStatus = (status: AuditStatus["status"], stepIndex: number, event: string, detail?: string) => {
      thread.status = status;
      thread.step_index = stepIndex;
      thread.updated_at = now();
      thread.timeline = [...thread.timeline, makeEvent(threadId, stepIndex, event, status, now(), detail)];
      this.save();
    };

    await this.delay(650);
    setStatus("FETCHED", 1, "Filing retrieved", "10-K filing metadata resolved");

    await this.delay(850);
    thread.metrics = company.metrics.map((m) => ({ ...m }));
    setStatus("EXTRACTED", 2, "Extraction complete", `${thread.metrics.length} metrics extracted from filing`);

    await this.delay(750);
    thread.validation_checks = this.buildValidationChecks(thread);
    thread.flagged_items = flagged.map((f) => ({ ...f }));
    for (const f of flagged) {
      thread.anomaly_explanations[f.metric_name] = buildAnomalyExplanation(f);
    }
    setStatus("VALIDATED", 3, "Confidence scoring and validation complete");

    const escalated: string[] = [];
    for (const m of thread.metrics) {
      const flaggedItem = flagged.find((f) => f.metric_name === m.metric_name);
      if (flaggedItem) {
        escalated.push(m.metric_name);
        continue;
      }
      if (m.confidence < thread.thresholds.confidence_threshold) {
        escalated.push(m.metric_name);
      }
    }

    if (willPause) {
      thread.metrics = thread.metrics.map((m) =>
        escalated.includes(m.metric_name) ? { ...m, decision_state: "FLAGGED" } : { ...m, decision_state: "PENDING" }
      );
      setStatus("PAUSED_FOR_REVIEW", 5, "Automated decision escalated to human review");
      return;
    }

    thread.metrics = thread.metrics.map((m) =>
      escalated.includes(m.metric_name) ? { ...m, decision_state: "FLAGGED" } : { ...m, decision_state: "AUTO_APPROVED" }
    );
    setStatus(
      "AUTO_APPROVED",
      6,
      "Automated decision approved",
      `${thread.metrics.filter((m) => m.decision_state === "AUTO_APPROVED").length} metrics auto-approved`
    );
    await this.delay(650);
    setStatus("COMPLETED", 8, "Audit completed");
    thread.accuracy_report = this.computeAccuracy(thread);
    await this.appendAutoApprovedRows(thread);
    this.save();
  }

  private buildValidationChecks(thread: StoredThread): AuditStatus["validation_checks"] {
    const checks: AuditStatus["validation_checks"] = [];
    for (const m of thread.metrics) {
      const flaggedItem = thread.flagged_items.find((f) => f.metric_name === m.metric_name);
      const status = flaggedItem ? "FAILED" : m.confidence >= thread.thresholds.confidence_threshold ? "PASSED" : "FAILED";
      checks.push({
        rule_name: flaggedItem ? flaggedItem.rules[0] ?? "FLAG_RULE" : "CONFIDENCE_GATE",
        metric_name: m.metric_name,
        status,
        reason: flaggedItem ? `Flagged: ${flaggedItem.reasons[0] ?? "validation failure"}` : `Confidence ${(m.confidence * 100).toFixed(0)}% within policy`,
        details: flaggedItem
          ? flaggedItem.reasons.join("; ")
          : `Confidence ${(m.confidence * 100).toFixed(0)}% above threshold ${(thread.thresholds.confidence_threshold * 100).toFixed(0)}%`,
        metrics_involved: [m.metric_name],
      });
    }
    return checks;
  }

  private computeAccuracy(thread: StoredThread): AccuracyReport {
    const company = findCompanyByCik(thread.cik);
    const tolerancePct = thread.thresholds.accounting_tolerance_pct * 100;

    interface Detail {
      metric: string;
      extracted: number;
      final: number;
      xbrl: number;
      match: boolean;
      diff_pct: number;
      extractedMatch: boolean;
      extractedDiff_pct: number;
    }

    const details: Detail[] = thread.metrics.map((m) => {
      const extracted = m.original_value;
      const final = m.value_usd;
      const xbrl = trueValueFor(company, m.metric_name);
      const diffPct = xbrl !== 0 ? Math.abs((final - xbrl) / xbrl) * 100 : 0;
      const extractedDiffPct = xbrl !== 0 ? Math.abs((extracted - xbrl) / xbrl) * 100 : 0;
      return {
        metric: m.metric_name,
        extracted,
        final,
        xbrl,
        match: diffPct <= tolerancePct,
        diff_pct: diffPct,
        extractedMatch: extractedDiffPct <= tolerancePct,
        extractedDiff_pct: extractedDiffPct,
      };
    });

    const accuracy = ratio(details.map((d) => d.match));
    const originalAccuracy = ratio(details.map((d) => d.extractedMatch));

    const autoApprovedMetrics = thread.metrics.filter((m) => m.decision_state === "AUTO_APPROVED");
    const autoApprovedDetails = details.filter(
      (d) => thread.metrics.find((m) => m.metric_name === d.metric)?.decision_state === "AUTO_APPROVED"
    );
    const autoApprovalAccuracy = ratio(autoApprovedDetails.map((d) => d.match));

    const resolvedEscalated = thread.metrics.filter(
      (m) => m.decision_state === "APPROVED" || m.decision_state === "CORRECTED" || m.decision_state === "REJECTED"
    );
    const escalationPrecision =
      resolvedEscalated.length > 0 ? ratio(resolvedEscalated.map((m) => details.find((d) => d.metric === m.metric_name)?.match ?? false)) : 100;

    const escalationPrecisionByType: Record<string, number> = {};
    for (const type of ["EXTRACTION_RISK", "FINANCIAL_ANOMALY"] as const) {
      const items = thread.flagged_items.filter(
        (f) => f.escalation_types.includes(type) && resolvedEscalated.some((m) => m.metric_name === f.metric_name)
      );
      const values = items.map((f) => details.find((d) => d.metric === f.metric_name)?.match ?? false);
      escalationPrecisionByType[type] = values.length > 0 ? ratio(values) : 0;
    }

    const deviating = details.filter((d) => d.extractedDiff_pct > tolerancePct);
    const resolvedCorrect = resolvedEscalated.filter((m) => details.find((d) => d.metric === m.metric_name)?.match).length;
    const escalationRecall = deviating.length > 0 ? (resolvedCorrect / deviating.length) * 100 : 100;

    const perMetricAccuracy: Record<string, number> = {};
    for (const d of details) {
      perMetricAccuracy[d.metric] = ratio([d.match]);
    }

    return {
      accuracy_pct: accuracy,
      original_accuracy_pct: originalAccuracy,
      auto_approval_accuracy_pct: autoApprovalAccuracy,
      auto_approved_count: autoApprovedMetrics.length,
      escalated_count: resolvedEscalated.length,
      escalation_precision_pct: escalationPrecision,
      escalation_precision_by_type: escalationPrecisionByType,
      escalation_recall_pct: escalationRecall,
      per_metric_accuracy: perMetricAccuracy,
      metric_details: details.map(({ metric, extracted, final, xbrl, match, diff_pct }) => ({ metric, extracted, final, xbrl, match, diff_pct })),
    };
  }

  private async appendAutoApprovedRows(thread: StoredThread) {
    let prevHash = GENESIS_HASH;
    for (const row of this.db.auditLogs) {
      prevHash = row.row_hash;
    }
    const now = new Date().toISOString();
    for (const m of thread.metrics) {
      if (m.decision_state !== "AUTO_APPROVED") continue;
      const row: AuditLogRow = {
        id: makeId("AL"),
        thread_id: thread.thread_id,
        company_name: thread.company_name,
        metric_name: m.metric_name,
        decision: "AUTO_APPROVED",
        original_value: m.original_value,
        corrected_value: m.value_usd,
        reviewer_notes: `Auto-approved: confidence ${(m.confidence * 100).toFixed(1)}% above threshold`,
        timestamp: now,
        prev_hash: prevHash,
        row_hash: "",
      };
      row.row_hash = await computeRowHash(prevHash, row);
      this.db.auditLogs.push(row);
      prevHash = row.row_hash;
    }
  }

  async resume(threadId: string, payload: ResumePayload): Promise<AuditStatus> {
    const thread = this.db.threads[threadId];
    if (!thread) throw new Error(`Thread ${threadId} not found`);
    await this.delay(400, 600);
    const decisionMap = new Map(payload.decisions.map((d) => [d.metric_name, d]));

    for (const m of thread.metrics) {
      const d = decisionMap.get(m.metric_name);
      if (!d) continue;
      const state = d.decision === "CORRECTED" ? "CORRECTED" : d.decision === "REJECTED" ? "REJECTED" : "APPROVED";
      const pre = m.value_usd;
      m.decision_state = state;
      m.original_value = pre;
      m.value_usd = d.corrected_value ?? pre;
    }

    thread.status = "HUMAN_REVIEWED";
    thread.updated_at = new Date().toISOString();
    thread.timeline = [
      ...thread.timeline,
      makeEvent(threadId, 5, "Human decisions recorded", "HUMAN_REVIEWED", thread.updated_at, `${payload.decisions.length} decisions submitted`),
    ];
    this.save();

    await this.delay(500);
    thread.status = "COMPLETED";
    thread.step_index = 6;
    thread.updated_at = new Date().toISOString();
    thread.timeline = [...thread.timeline, makeEvent(threadId, 6, "Decision and resume complete", "COMPLETED", thread.updated_at)];
    thread.accuracy_report = this.computeAccuracy(thread);
    await this.appendDecisionRows(thread, payload.decisions);
    this.save();
    return toStatus(thread);
  }

  private async appendDecisionRows(thread: StoredThread, decisions: ResumePayload["decisions"]) {
    let prevHash = GENESIS_HASH;
    for (const row of this.db.auditLogs) {
      prevHash = row.row_hash;
    }
    const now = new Date().toISOString();
    for (const d of decisions) {
      const m = thread.metrics.find((x) => x.metric_name === d.metric_name);
      const row: AuditLogRow = {
        id: makeId("AL"),
        thread_id: thread.thread_id,
        company_name: thread.company_name,
        metric_name: d.metric_name,
        decision: d.decision,
        original_value: m?.original_value ?? 0,
        corrected_value: d.corrected_value ?? m?.value_usd ?? 0,
        reviewer_notes: d.reviewer_notes ?? "",
        timestamp: now,
        prev_hash: prevHash,
        row_hash: "",
      };
      row.row_hash = await computeRowHash(prevHash, row);
      this.db.auditLogs.push(row);
      prevHash = row.row_hash;
    }
  }

  async listThreads(): Promise<ThreadSummary[]> {
    await this.delay(250, 400);
    const summaries: ThreadSummary[] = Object.values(this.db.threads).map((t) => ({
      thread_id: t.thread_id,
      company_name: t.company_name,
      ticker: t.ticker,
      cik: t.cik,
      fiscal_year: t.fiscal_year,
      status: t.status,
      flagged_count: t.flagged_items.length,
      auto_approved_count: t.metrics.filter((m) => m.decision_state === "AUTO_APPROVED").length,
      created_at: t.created_at,
      updated_at: t.updated_at,
      demo_only: t.demo_only,
      accuracy_pct: t.accuracy_report?.accuracy_pct ?? undefined,
      original_accuracy_pct: t.accuracy_report?.original_accuracy_pct,
      auto_approval_accuracy_pct: t.accuracy_report?.auto_approval_accuracy_pct,
      escalation_precision_pct: t.accuracy_report?.escalation_precision_pct,
      escalation_recall_pct: t.accuracy_report?.escalation_recall_pct,
      escalation_precision_by_type: t.accuracy_report?.escalation_precision_by_type,
      metric_details: t.accuracy_report?.metric_details,
    }));
    return summaries.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  async getStatus(threadId: string): Promise<AuditStatus> {
    const thread = this.db.threads[threadId];
    if (!thread) throw new Error(`Thread ${threadId} not found`);
    await this.delay(150, 300);
    return toStatus(thread);
  }

  async getTimeline(threadId: string): Promise<AuditEvent[]> {
    const thread = this.db.threads[threadId];
    if (!thread) throw new Error(`Thread ${threadId} not found`);
    await this.delay(150, 300);
    return [...thread.timeline].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  }

  async listAuditLogs(filters?: AuditLogFilters): Promise<AuditLogRow[]> {
    await this.delay(200, 350);
    let rows = [...this.db.auditLogs];
    if (filters?.thread_id) rows = rows.filter((r) => r.thread_id === filters.thread_id);
    if (filters?.company_name) rows = rows.filter((r) => r.company_name.toLowerCase().includes(filters.company_name!.toLowerCase()));
    if (filters?.decision) rows = rows.filter((r) => r.decision === filters.decision);
    return rows;
  }

  async verifyChain(): Promise<VerifyResult> {
    const result = await verifyChain(this.db.auditLogs);
    await this.delay(250, 400);
    return result;
  }

  async resetDemo(): Promise<void> {
    this.db = { threads: {}, auditLogs: [] };
    this.save();
  }

  async tamperWithLastRow(): Promise<VerifyResult> {
    const last = this.db.auditLogs[this.db.auditLogs.length - 1];
    if (last) {
      last.original_value = Math.round((last.original_value + 12345.67) * 100) / 100;
      this.save();
    }
    return verifyChain(this.db.auditLogs);
  }

  async setFailureMode(enabled: boolean): Promise<void> {
    this.failureMode = enabled;
  }
}






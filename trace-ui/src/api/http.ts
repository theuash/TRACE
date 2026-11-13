import type { TraceApi } from "./contract";
import type {
  AccuracyReport,
  AnomalyExplanation,
  AuditEvent,
  AuditLogFilters,
  AuditLogRow,
  AuditStatus,
  CompanyInfo,
  DatabaseInfo,
  DatabaseStatus,
  EscalationEstimate,
  HealthResponse,
  ResumePayload,
  StartAuditRequest,
  ThreadSummary,
  Thresholds,
  VerifyResult,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const body = (await response.json().catch(() => null)) as T | null;
  if (!response.ok) {
    throw new Error(body ? (body as { detail?: string }).detail ?? `Request failed with status ${response.status}` : `Request failed with status ${response.status}`);
  }
  return body as T;
}

export class HttpTraceApi implements TraceApi {
  async health(): Promise<HealthResponse> {
    const res = await request<HealthResponse>("/health");
    return res;
  }

  async listCompanies(): Promise<CompanyInfo[]> {
    return request<CompanyInfo[]>("/companies");
  }

  async searchCompanies(query: string): Promise<CompanyInfo[]> {
    // Any company on EDGAR, not just the five the demo configures.
    return request<CompanyInfo[]>(`/companies/search?q=${encodeURIComponent(query)}`);
  }

  async startAudit(payload: StartAuditRequest): Promise<AuditStatus> {
    return request<AuditStatus>("/audits", { method: "POST", body: JSON.stringify(payload) });
  }

  async listThreads(): Promise<ThreadSummary[]> {
    return request<ThreadSummary[]>("/threads");
  }

  async getStatus(threadId: string): Promise<AuditStatus> {
    return request<AuditStatus>(`/threads/${threadId}/status`);
  }

  async getTimeline(threadId: string): Promise<AuditEvent[]> {
    return request<AuditEvent[]>(`/threads/${threadId}/timeline`);
  }

  async resume(threadId: string, payload: ResumePayload): Promise<AuditStatus> {
    return request<AuditStatus>(`/threads/${threadId}/resume`, { method: "POST", body: JSON.stringify(payload) });
  }

  async listAuditLogs(filters?: AuditLogFilters): Promise<AuditLogRow[]> {
    const query = new URLSearchParams();
    if (filters?.thread_id) query.set("thread_id", filters.thread_id);
    if (filters?.company_name) query.set("company_name", filters.company_name);
    if (filters?.decision) query.set("decision", filters.decision);
    const qs = query.toString();
    return request<AuditLogRow[]>(`/audit-logs${qs ? `?${qs}` : ""}`);
  }

  async verifyChain(): Promise<VerifyResult> {
    return request<VerifyResult>("/audit-logs/verify");
  }

  async getReport(): Promise<AccuracyReport | null> {
    return request<AccuracyReport | null>("/report");
  }

  async getThresholds(): Promise<Thresholds> {
    return request<Thresholds>("/thresholds");
  }

  async setThresholds(thresholds: Thresholds): Promise<Thresholds> {
    return request<Thresholds>("/thresholds", {
      method: "POST",
      body: JSON.stringify(thresholds),
    });
  }

  async estimateEscalations(thresholds: Thresholds): Promise<EscalationEstimate> {
    return request<EscalationEstimate>("/thresholds/estimate", {
      method: "POST",
      body: JSON.stringify(thresholds),
    });
  }

  async getDatabase(): Promise<DatabaseInfo> {
    return request<DatabaseInfo>("/database");
  }

  async pingDatabase(): Promise<DatabaseStatus> {
    return request<DatabaseStatus>("/database/ping", { method: "POST" });
  }
}

export type { AccuracyReport, AnomalyExplanation };

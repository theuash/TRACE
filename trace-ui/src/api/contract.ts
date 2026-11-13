import type {
  AccuracyReport,
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

export interface TraceApi {
  health(): Promise<HealthResponse>;
  listCompanies(): Promise<CompanyInfo[]>;
  searchCompanies(query: string): Promise<CompanyInfo[]>;
  startAudit(request: StartAuditRequest): Promise<AuditStatus>;
  listThreads(): Promise<ThreadSummary[]>;
  getStatus(threadId: string): Promise<AuditStatus>;
  getTimeline(threadId: string): Promise<AuditEvent[]>;
  resume(threadId: string, payload: ResumePayload): Promise<AuditStatus>;
  listAuditLogs(filters?: AuditLogFilters): Promise<AuditLogRow[]>;
  verifyChain(): Promise<VerifyResult>;
  getReport(): Promise<AccuracyReport | null>;
  getThresholds(): Promise<Thresholds>;
  setThresholds(thresholds: Thresholds): Promise<Thresholds>;
  estimateEscalations(thresholds: Thresholds): Promise<EscalationEstimate>;
  getDatabase(): Promise<DatabaseInfo>;
  pingDatabase(): Promise<DatabaseStatus>;
}

import type {
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
} from "./types";

export interface TraceApi {
  health(): Promise<HealthResponse>;
  listCompanies(): Promise<CompanyInfo[]>;
  startAudit(request: StartAuditRequest): Promise<AuditStatus>;
  listThreads(): Promise<ThreadSummary[]>;
  getStatus(threadId: string): Promise<AuditStatus>;
  getTimeline(threadId: string): Promise<AuditEvent[]>;
  resume(threadId: string, payload: ResumePayload): Promise<AuditStatus>;
  listAuditLogs(filters?: AuditLogFilters): Promise<AuditLogRow[]>;
  verifyChain(): Promise<VerifyResult>;
  resetDemo(): Promise<void>;
  tamperWithLastRow(): Promise<VerifyResult>;
  setFailureMode(enabled: boolean): Promise<void>;
}

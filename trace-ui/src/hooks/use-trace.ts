import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createTraceApi } from "../api/client";
import type { AuditLogFilters, StartAuditRequest, Thresholds } from "../api/types";

export const api = createTraceApi();

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
  });
}

export function useCompanies() {
  return useQuery({
    queryKey: ["companies"],
    queryFn: () => api.listCompanies(),
  });
}

export function useCompanySearch(query: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["companies", "search", trimmed],
    queryFn: () => api.searchCompanies(trimmed),
    enabled: trimmed.length >= 2,
    staleTime: 60_000,
    retry: false,
  });
}

export function useThreads() {
  return useQuery({
    queryKey: ["threads"],
    queryFn: () => api.listThreads(),
  });
}

export function useThreadStatus(threadId: string | null | undefined) {
  return useQuery({
    queryKey: ["thread", threadId],
    queryFn: () => api.getStatus(threadId as string),
    enabled: Boolean(threadId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status) return false;
      if (status === "COMPLETED" || status === "FAILED") return false;
      return 2_000;
    },
  });
}

export function useThreadTimeline(threadId: string | null | undefined) {
  return useQuery({
    queryKey: ["thread-timeline", threadId],
    queryFn: () => api.getTimeline(threadId as string),
    enabled: Boolean(threadId),
  });
}

export function useAuditLogs(filters?: AuditLogFilters) {
  return useQuery({
    queryKey: ["audit-logs", filters ?? {}],
    queryFn: () => api.listAuditLogs(filters),
  });
}

export function useVerifyChain() {
  return useQuery({
    queryKey: ["audit-logs", "verify"],
    queryFn: () => api.verifyChain(),
  });
}

export function useStartAudit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: StartAuditRequest) => api.startAudit(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });
}

export function useResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ threadId, payload }: { threadId: string; payload: { decisions: { metric_name: string; decision: "APPROVED" | "CORRECTED" | "REJECTED"; corrected_value?: number; reviewer_notes?: string }[] } }) =>
      api.resume(threadId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });
}


export function useReport() {
  return useQuery({
    queryKey: ["report"],
    queryFn: () => api.getReport(),
    // The report is a verification run: expensive and stable between decisions.
    staleTime: 30_000,
  });
}

export function useThresholds() {
  return useQuery({
    queryKey: ["thresholds"],
    queryFn: () => api.getThresholds(),
    staleTime: 10_000,
  });
}

export function useSetThresholds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (thresholds: Thresholds) => api.setThresholds(thresholds),
    onSuccess: (saved) => {
      queryClient.setQueryData(["thresholds"], saved);
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });
}

export function useEstimateEscalations() {
  return useMutation({
    mutationFn: (thresholds: Thresholds) => api.estimateEscalations(thresholds),
  });
}

export function useDatabase() {
  return useQuery({
    queryKey: ["database"],
    queryFn: () => api.getDatabase(),
    // The database panel is a status display: a stale second is fine, a cold Neon project is not.
    staleTime: 10_000,
    retry: 1,
  });
}

export function usePingDatabase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.pingDatabase(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["database"] });
    },
  });
}

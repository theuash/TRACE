import { Badge } from "@/components/ui/badge";
import type { AuditStatusValue, DecisionState, EscalationType } from "@/api/types";
import { cn } from "@/lib/utils";

const statusConfig: Record<AuditStatusValue, { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "danger" | "info" | "muted" }> = {
  STARTED: { label: "Started", variant: "muted" },
  FETCHED: { label: "Fetched", variant: "info" },
  EXTRACTED: { label: "Extracted", variant: "info" },
  VALIDATED: { label: "Validated", variant: "info" },
  PAUSED_FOR_REVIEW: { label: "Paused for review", variant: "warning" },
  HUMAN_REVIEWED: { label: "Human reviewed", variant: "info" },
  AUTO_APPROVED: { label: "Auto-approved", variant: "success" },
  COMPLETED: { label: "Completed", variant: "success" },
  FAILED: { label: "Failed", variant: "danger" },
};

export function StatusBadge({ status }: { status: AuditStatusValue }) {
  const config = statusConfig[status];
  return <Badge variant={config.variant} data-testid={`status-${status}`}>{config.label}</Badge>;
}

const decisionConfig: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "danger" | "info" | "muted" }> = {
  AUTO_APPROVED: { label: "Auto-approved", variant: "success" },
  APPROVED: { label: "Approved", variant: "info" },
  CORRECTED: { label: "Corrected", variant: "warning" },
  REJECTED: { label: "Rejected", variant: "danger" },
};

export function DecisionBadge({ decision }: { decision: string }) {
  const config = decisionConfig[decision] ?? { label: decision, variant: "secondary" as const };
  return <Badge variant={config.variant} data-testid={`decision-${decision}`}>{config.label}</Badge>;
}

const escalationVariant: Record<EscalationType, "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "danger" | "info" | "muted"> = {
  EXTRACTION_RISK: "warning",
  FINANCIAL_ANOMALY: "danger",
};

export function EscalationBadge({ type }: { type: EscalationType }) {
  return <Badge variant={escalationVariant[type]} data-testid={`escalation-${type}`}>{type.replace(/_/g, " ")}</Badge>;
}

export function DecisionStateBadge({ state }: { state: DecisionState }) {
  const map: Record<DecisionState, { label: string; className: string }> = {
    FLAGGED: { label: "Flagged", className: "bg-danger/15 text-danger" },
    PENDING: { label: "Pending", className: "bg-muted text-muted-foreground" },
    AUTO_APPROVED: { label: "Auto-approved", className: "bg-success/15 text-success" },
    APPROVED: { label: "Approved", className: "bg-info/15 text-info" },
    CORRECTED: { label: "Corrected", className: "bg-warning/15 text-warning" },
    REJECTED: { label: "Rejected", className: "bg-danger/15 text-danger" },
  };
  const config = map[state];
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", config.className)} data-testid={`decision-state-${state}`}>
      {config.label}
    </span>
  );
}

export function ConfidenceBadge({ confidence, label }: { confidence: number; label: "HIGH" | "LOW" }) {
  const tone = label === "HIGH" ? "bg-success/15 text-success" : "bg-danger/15 text-danger";
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", tone)} data-testid="confidence-badge">
      {label} confidence · {(confidence * 100).toFixed(0)}%
    </span>
  );
}

/**
 * Risk tier. The tier is computed by the workflow (confidence AND validation results) and sent
 * by the API - the UI only colours it, it never decides it.
 */
export function TierBadge({ tier }: { tier?: "red" | "yellow" | "green" }) {
  if (!tier) return null;
  const config = {
    red: { label: "Critical", className: "bg-danger text-danger-foreground" },
    yellow: { label: "Review", className: "bg-warning/20 text-warning" },
    green: { label: "Low risk", className: "bg-success/15 text-success" },
  }[tier];
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", config.className)} data-testid={`tier-${tier}`}>
      {config.label}
    </span>
  );
}

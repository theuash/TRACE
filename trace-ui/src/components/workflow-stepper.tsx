import type { AuditStatusValue } from "@/api/types";

export interface WorkflowStepState {
  key: string;
  label: string;
  state: "done" | "active" | "failed" | "upcoming" | "skipped";
}

const stepLabels = [
  "Filing retrieval",
  "Extraction",
  "Confidence scoring",
  "Validation",
  "Automated decision",
  "Human review",
  "Decision and resume",
  "XBRL verification",
  "Audit history",
];

function statesFor(status: AuditStatusValue): WorkflowStepState[] {
  const failedStep = 2;
  switch (status) {
    case "STARTED":
      return stepLabels.map((label, index) => ({ key: `step-${index}`, label, state: index === 0 ? "active" : "upcoming" }));
    case "FETCHED":
      return stepLabels.map((label, index) => ({ key: `step-${index}`, label, state: index <= 0 ? "done" : "upcoming" }));
    case "EXTRACTED":
      return stepLabels.map((label, index) => ({ key: `step-${index}`, label, state: index <= 1 ? "done" : index === 2 ? "active" : "upcoming" }));
    case "VALIDATED":
      return stepLabels.map((label, index) => ({ key: `step-${index}`, label, state: index <= 3 ? "done" : index === 4 ? "active" : "upcoming" }));
    case "PAUSED_FOR_REVIEW":
      return stepLabels.map((label, index) =>
        index <= 4 ? { key: `step-${index}`, label, state: "done" as const } : { key: `step-${index}`, label, state: index === 5 ? ("active" as const) : ("upcoming" as const) }
      );
    case "HUMAN_REVIEWED":
      return stepLabels.map((label, index) =>
        index <= 5 ? { key: `step-${index}`, label, state: "done" as const } : { key: `step-${index}`, label, state: index === 6 ? ("active" as const) : ("upcoming" as const) }
      );
    case "AUTO_APPROVED":
      return stepLabels.map((label, index) =>
        index <= 4
          ? { key: `step-${index}`, label, state: "done" as const }
          : index === 5
            ? { key: `step-${index}`, label, state: "skipped" as const }
            : { key: `step-${index}`, label, state: index === 6 ? ("active" as const) : "upcoming" as const }
      );
    case "COMPLETED":
      return stepLabels.map((label, index) => ({ key: `step-${index}`, label, state: "done" as const }));
    case "FAILED":
      return stepLabels.map((label, index) =>
        index < failedStep ? { key: `step-${index}`, label, state: "done" as const } : index === failedStep ? { key: `step-${index}`, label, state: "failed" as const } : { key: `step-${index}`, label, state: "upcoming" as const }
      );
  }
}

export function WorkflowStepper({ status }: { status: AuditStatusValue }) {
  const steps = statesFor(status);
  return (
    <ol className="flex flex-wrap items-center gap-2" data-testid="workflow-stepper">
      {steps.map((step, index) => (
        <li key={step.key} className="flex items-center gap-2">
          {index > 0 && <span className={`h-px w-6 ${step.state === "done" || step.state === "failed" ? "bg-success" : "bg-border"}`} aria-hidden="true" />}
          <span
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
              step.state === "done"
                ? "border-success/40 bg-success/10 text-success"
                : step.state === "active"
                  ? "border-info/50 bg-info/10 text-info"
                  : step.state === "failed"
                    ? "border-danger/50 bg-danger/10 text-danger"
                    : step.state === "skipped"
                      ? "border-border bg-muted text-muted-foreground"
                      : "border-border bg-background text-muted-foreground"
            }`}
            data-testid={`workflow-step-${step.key}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                step.state === "done" ? "bg-success" : step.state === "active" ? "bg-info" : step.state === "failed" ? "bg-danger" : "bg-muted-foreground/40"
              }`}
              aria-hidden="true"
            />
            {step.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

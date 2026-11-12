import { cn } from "@/lib/utils";
import type { ConfidenceSignals } from "@/api/types";

interface ConfidenceBarProps {
  value: number;
  label?: "HIGH" | "LOW";
  signals?: ConfidenceSignals | Record<string, number | null>;
  id?: string;
}

const signalKeys = [
  "snippet_grounding",
  "concept_match",
  "unit_consistency",
  "period_consistency",
  "prior_year_sanity",
  "extractor_agreement",
  "column_period",
  "cross_statement",
  "llm_confidence",
];

export function ConfidenceBar({ value, label, signals, id }: ConfidenceBarProps) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone = label === "HIGH" ? "bg-success" : "bg-danger";
  return (
    <div className="w-full" data-testid={`confidence-bar-${id ?? "default"}`}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">Confidence</span>
        <span className="text-xs font-semibold text-foreground">{label === "HIGH" ? "High" : "Low"} · {(value * 100).toFixed(0)}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-secondary" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        <div className={cn("h-full rounded-full transition-all", tone)} style={{ width: `${pct}%` }} />
      </div>
      {signals && (
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {signalKeys.map((key) => {
            const raw = (signals as Record<string, number | null> | undefined)?.[key] ?? null;
            const numeric = typeof raw === "number" ? raw : null;
            const signalPct = numeric === null ? 0 : numeric * 100;
            return (
              <div key={key} className="flex items-center gap-1.5" title={`${key.replace(/_/g, " ")}: ${numeric === null ? "n/a" : `${signalPct.toFixed(0)}%`}`}>
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" aria-hidden="true" />
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{key.replace(/_/g, " ")}</span>
                <span className="text-[10px] font-medium text-foreground">{numeric === null ? "—" : `${signalPct.toFixed(0)}%`}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

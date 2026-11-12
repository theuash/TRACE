import { FlaskConical } from "lucide-react";
import { useDataMode } from "@/hooks/use-trace";
import { cn } from "@/lib/utils";

export function DemoPill() {
  const { mode, healthStatus } = useDataMode();
  const live = mode === "http";
  return (
    <span
      data-testid="demo-pill"
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium",
        live ? "border-success/40 bg-success/10 text-success" : "border-warning/40 bg-warning/10 text-warning"
      )}
      title={live ? "Connected to the TRACE API" : "Using built-in demo data — no backend required"}
    >
      <span
        className={cn("h-1.5 w-1.5 rounded-full", live ? "bg-success" : "bg-warning", healthStatus === "ok" && !live ? "animate-pulse" : "")}
        aria-hidden="true"
      />
      {live ? "Live" : "Demo data"}
    </span>
  );
}

export function DemoPillFooter() {
  const { mode } = useDataMode();
  return (
    <span className="text-xs text-muted-foreground">{mode === "http" ? "Live API" : "Demo data"}</span>
  );
}

export function FlaskConicalIcon() {
  return <FlaskConical className="h-4 w-4" aria-hidden="true" />;
}

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon?: ReactNode;
  tone?: "default" | "success" | "warning" | "danger" | "info";
  dataTestId?: string;
}

export function KpiCard({ title, value, subtitle, icon, tone = "default", dataTestId }: KpiCardProps) {
  const toneClasses = {
    default: "text-foreground",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
    info: "text-info",
  }[tone];
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm" data-testid={dataTestId ?? `kpi-${title.replace(/\W+/g, "-").toLowerCase()}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</span>
        {icon ? <span className={cn("text-muted-foreground", toneClasses)} aria-hidden="true">{icon}</span> : null}
      </div>
      <div className="mt-2 font-sans text-2xl font-semibold tabular-nums tracking-tight text-foreground">{value}</div>
      {subtitle ? <div className="mt-1 text-xs text-muted-foreground">{subtitle}</div> : null}
    </div>
  );
}

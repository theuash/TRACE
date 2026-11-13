import { useEffect, useMemo, useState } from "react";
import {
  useDatabase,
  useEstimateEscalations,
  useHealth,
  usePingDatabase,
  useSetThresholds,
  useThresholds,
} from "@/hooks/use-trace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "@/components/theme-provider";
import { formatDateTime } from "@/lib/format";
import { toast } from "sonner";
import type { Thresholds } from "@/api/types";

const FALLBACK_THRESHOLDS: Thresholds = {
  confidence_threshold: 0.85,
  confidence_critical: 0.6,
  yoy_change_pct: 40,
  accounting_tolerance_pct: 0.1,
  segment_tolerance_pct: 0.1,
};

export function SettingsPage() {
  const { data: health, error: healthError, refetch: refetchHealth } = useHealth();
  const { data: database, error: databaseError } = useDatabase();
  const ping = usePingDatabase();
  const { data: thresholds } = useThresholds();
  const save = useSetThresholds();
  const estimate = useEstimateEscalations();
  const { theme, toggleTheme } = useTheme();
  const [draft, setDraft] = useState<Thresholds>(FALLBACK_THRESHOLDS);

  useEffect(() => {
    if (thresholds) setDraft(thresholds);
  }, [thresholds]);

  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(thresholds ?? FALLBACK_THRESHOLDS),
    [draft, thresholds]
  );

  const connectionOk = health?.status === "ok" || health?.status === "healthy";

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">Data source and policy defaults.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Data source</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">Current mode</span>
            <Badge variant={health?.mode === "real" || !health?.mode ? "success" : "warning"}>
              {health?.mode === "real" || !health?.mode ? "Live data" : "Fixtures"}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Connection status</span>
            <span
              className={`text-sm font-medium ${
                healthError ? "text-danger" : connectionOk ? "text-success" : "text-muted-foreground"
              }`}
            >
              {healthError ? "Unreachable" : health ? (connectionOk ? "Healthy" : "Degraded") : "Checking…"}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">Base URL: {import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"}</div>
          <Button variant="outline" size="sm" onClick={() => void refetchHealth()}>
            Test connection
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Policy thresholds</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <p className="text-sm text-muted-foreground">
            Values below the confidence threshold escalate to a human. Every applied change is written to the audit log.
          </p>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <label htmlFor="confidence-threshold">Confidence threshold</label>
              <span className="rounded-full bg-accent px-2 py-0.5 font-semibold tabular-nums" data-testid="confidence-value">
                {Math.round(draft.confidence_threshold * 100)}%
              </span>
            </div>
            <Slider
              id="confidence-threshold"
              min={50}
              max={99}
              step={1}
              value={[Math.round(draft.confidence_threshold * 100)]}
              onValueChange={([value]) => setDraft((d) => ({ ...d, confidence_threshold: value / 100 }))}
              aria-label="Confidence threshold"
            />
            <p className="text-xs text-muted-foreground">
              Auto-approve at {Math.round(draft.confidence_threshold * 100)}% confidence or better.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <label htmlFor="critical-threshold">Critical threshold</label>
              <span className="rounded-full bg-danger/15 px-2 py-0.5 font-semibold tabular-nums text-danger" data-testid="critical-value">
                {Math.round(draft.confidence_critical * 100)}%
              </span>
            </div>
            <Slider
              id="critical-threshold"
              min={30}
              max={95}
              step={1}
              value={[Math.round(draft.confidence_critical * 100)]}
              onValueChange={([value]) => setDraft((d) => ({ ...d, confidence_critical: value / 100 }))}
              aria-label="Critical threshold"
            />
          </div>

          <div className="flex items-center justify-between gap-4 text-sm">
            <label htmlFor="yoy-tolerance">YoY change tolerance (%)</label>
            <input
              id="yoy-tolerance"
              type="number"
              min={1}
              max={200}
              step={1}
              className="w-24 rounded-md border bg-background px-2 py-1 text-right tabular-nums"
              value={draft.yoy_change_pct}
              onChange={(e) => setDraft((d) => ({ ...d, yoy_change_pct: Number(e.target.value) || 0 }))}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={estimate.isPending}
              onClick={() =>
                void estimate.mutateAsync(draft).then((r) =>
                  toast(`${r.escalations} value(s) would escalate at these settings`)
                )
              }
            >
              {estimate.isPending ? "Estimating…" : "Estimate impact"}
            </Button>
            <Button
              size="sm"
              disabled={save.isPending || !dirty}
              onClick={() =>
                void save.mutateAsync(draft).then((saved) => {
                  setDraft(saved);
                  toast.success("Thresholds applied and recorded in the audit log");
                })
              }
            >
              Apply thresholds
            </Button>
            {dirty ? <span className="text-xs text-warning">Unsaved change</span> : null}
            {estimate.data ? (
              <span className="text-xs text-muted-foreground" data-testid="estimate-result">
                {estimate.data.escalations} value(s) would escalate
              </span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data store</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Where the runs, the side effects and the audit chain live.
          </p>
          {database ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-full bg-accent px-2 py-0.5 font-semibold">
                  {database.backend === "postgresql" ? "PostgreSQL" : database.backend}
                </span>
                {database.host ? <span className="font-mono text-xs text-muted-foreground">{database.host}</span> : null}
                <Badge variant={database.ok ? "success" : "danger"} data-testid="db-state">
                  {database.ok ? "connected" : "unreachable"}
                </Badge>
                {database.latency_ms !== null ? (
                  <span className="text-xs text-muted-foreground">{database.latency_ms} ms</span>
                ) : null}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-4 font-medium">Table</th>
                      <th className="py-2 pr-4 font-medium">Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(database.tables).map(([table, count]) => (
                      <tr key={table} className="border-b last:border-0">
                        <td className="py-1.5 pr-4 font-mono text-xs">{table}</td>
                        <td className="py-1.5 pr-4 tabular-nums">{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="text-xs text-muted-foreground">
                {database.last_audit_write ? `Last audit row: ${formatDateTime(database.last_audit_write)}` : "No audit rows yet"}
                {database.last_run_write ? ` · Last run: ${formatDateTime(database.last_run_write)}` : ""}
              </div>
            </div>
          ) : databaseError ? (
            <p className="text-sm text-danger">The database did not answer: {String(databaseError)}</p>
          ) : (
            <p className="text-sm text-muted-foreground">Checking the database…</p>
          )}
          <Button variant="outline" size="sm" onClick={() => void ping.mutateAsync()} disabled={ping.isPending}>
            {ping.isPending ? "Pinging…" : "Ping the database"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between">
          <span className="text-sm">Theme</span>
          <Button variant="outline" size="sm" onClick={toggleTheme}>
            Switch to {theme === "dark" ? "light" : "dark"} theme
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

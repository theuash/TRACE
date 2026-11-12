import { useMemo, useState } from "react";
import { Crosshair } from "lucide-react";
import { useThreads } from "@/hooks/use-trace";
import { KpiCard } from "@/components/kpi-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPercent, formatUsdFull } from "@/lib/format";
import type { MetricAccuracyDetail } from "@/api/types";

export function AccuracyPage() {
  const { data: threads, isLoading, error } = useThreads();
  const [includeDemo, setIncludeDemo] = useState(false);
  const [computedOpen, setComputedOpen] = useState(false);

  const reports = useMemo(
    () => (threads ?? []).filter((t) => t.accuracy_pct != null).filter((t) => includeDemo || !t.demo_only),
    [threads, includeDemo]
  );

  const accuracyValues = reports.map((t) => t.accuracy_pct ?? 0);
  const finalAccuracy = accuracyValues.length ? accuracyValues.reduce((a, b) => a + b, 0) / accuracyValues.length : 0;
  const originalAccuracy = reports.map((t) => t.original_accuracy_pct ?? 0);
  const originalAvg = originalAccuracy.length ? originalAccuracy.reduce((a, b) => a + b, 0) / originalAccuracy.length : 0;
  const autoApprovalAccuracy = reports.map((t) => t.auto_approval_accuracy_pct ?? 0);
  const autoApprovalAvg = autoApprovalAccuracy.length ? autoApprovalAccuracy.reduce((a, b) => a + b, 0) / autoApprovalAccuracy.length : 0;
  const precisionValues = reports.map((t) => t.escalation_precision_pct ?? 0);
  const precisionAvg = precisionValues.length ? precisionValues.reduce((a, b) => a + b, 0) / precisionValues.length : 0;

  const chartData = reports.map((t) => ({
    ticker: t.ticker,
    accuracy: t.accuracy_pct ?? 0,
  }));

  const metricDetails: MetricAccuracyDetail[] = useMemo(() => {
    const out: MetricAccuracyDetail[] = [];
    for (const t of reports) {
      for (const d of t.metric_details ?? []) {
        out.push({ ...d });
      }
    }
    return out;
  }, [reports]);

  const exportCsv = () => {
    const header = ["metric", "extracted", "final", "xbrl", "match", "diff_pct"];
    const lines = metricDetails.map((d) => [d.metric, String(d.extracted), String(d.final), String(d.xbrl), String(d.match), String(d.diff_pct)]);
    const csv = [header, ...lines].map((l) => l.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trace-accuracy.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return <div className="space-y-4">Loading accuracy…</div>;
  }

  if (error || !threads) {
    return (
      <div className="rounded-xl border p-6 text-sm">
        Failed to load accuracy.
        <Button variant="outline" size="sm" className="ml-3">Retry</Button>
      </div>
    );
  }

  const firstReport = reports[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Accuracy</h2>
          <Badge variant="secondary">Final vs XBRL</Badge>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Switch checked={includeDemo} onCheckedChange={setIncludeDemo} aria-label="Include demo runs" />
            Include demo-only runs
          </label>
          <Button variant="outline" size="sm" onClick={exportCsv} disabled={metricDetails.length === 0}>
            Export CSV
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard title="Final accuracy" value={formatPercent(finalAccuracy, 1)} subtitle="Final values vs XBRL" icon={<Crosshair className="h-4 w-4" />} dataTestId="acc-final" />
        <KpiCard title="Original accuracy" value={formatPercent(originalAvg, 1)} subtitle="Pre-human-review values vs XBRL" icon={<Crosshair className="h-4 w-4" />} tone="info" dataTestId="acc-original" />
        <KpiCard title="Auto-approval accuracy" value={formatPercent(autoApprovalAvg, 1)} subtitle="Automated decisions that held" icon={<Crosshair className="h-4 w-4" />} tone="success" dataTestId="acc-auto" />
        <KpiCard title="Escalation precision" value={formatPercent(precisionAvg, 1)} subtitle="Escalated items resolved correctly" icon={<Crosshair className="h-4 w-4" />} tone="warning" dataTestId="acc-precision" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Accuracy by company</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-72 w-full" data-testid="accuracy-by-company-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="ticker" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="accuracy" name="Accuracy" fill="hsl(243.2 47.2% 40.4%)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Per-metric accuracy</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Metric</th>
                <th className="py-2 pr-4 font-medium">Extracted</th>
                <th className="py-2 pr-4 font-medium">Final</th>
                <th className="py-2 pr-4 font-medium">XBRL</th>
                <th className="py-2 pr-4 font-medium">Match</th>
                <th className="py-2 pr-4 font-medium">Diff %</th>
              </tr>
            </thead>
            <tbody>
              {metricDetails.map((d, i) => (
                <tr key={`${d.metric}-${i}`} className="border-b last:border-0">
                  <td className="py-2.5 pr-4 font-medium">{d.metric}</td>
                  <td className="py-2.5 pr-4 tabular-nums">{formatUsdFull(d.extracted)}</td>
                  <td className="py-2.5 pr-4 tabular-nums">{formatUsdFull(d.final)}</td>
                  <td className="py-2.5 pr-4 tabular-nums">{formatUsdFull(d.xbrl)}</td>
                  <td className="py-2.5 pr-4">{d.match ? <Badge variant="success">Match</Badge> : <Badge variant="danger">Mismatch</Badge>}</td>
                  <td className="py-2.5 pr-4 tabular-nums">{d.diff_pct.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>How these numbers are computed</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            Final accuracy compares post-human-review values against XBRL-reported figures. Original accuracy compares pre-review extracted
            values. Auto-approval accuracy measures automated decisions. Escalation precision measures how often escalated items were resolved
            correctly; recall measures whether truly deviating values were caught.
          </p>
          <Button variant="outline" size="sm" onClick={() => setComputedOpen((v) => !v)}>
            {computedOpen ? "Hide" : "Show"} computation detail
          </Button>
          {computedOpen ? (
            <div className="space-y-2 rounded-xl border p-4">
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Escalation precision by type</div>
                  <div className="mt-1 space-y-1">
                    {Object.entries(firstReport?.escalation_precision_by_type ?? {}).map(([type, value]) => (
                      <div key={type} className="flex items-center justify-between text-sm">
                        <span>{type.replace(/_/g, " ")}</span>
                        <span className="tabular-nums">{formatPercent(value, 1)}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Recall</div>
                  <div className="mt-1 text-sm tabular-nums">{formatPercent(firstReport?.escalation_recall_pct ?? 0, 1)}</div>
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

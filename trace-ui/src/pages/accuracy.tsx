import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Crosshair, Scale } from "lucide-react";
import { useReport, useThreads } from "@/hooks/use-trace";
import { KpiCard } from "@/components/kpi-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPercent, formatUsdFull } from "@/lib/format";
import { latestRunPerTicker } from "@/lib/threads";
import type { MetricAccuracyDetail } from "@/api/types";

export function AccuracyPage() {
  const navigate = useNavigate();
  const { data: report, isLoading, error } = useReport();
  const { data: threads } = useThreads();
  const [computedOpen, setComputedOpen] = useState(false);

  const companyNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const t of threads ?? []) map[t.ticker] = t.company_name;
    return map;
  }, [threads]);

  const metricDetails: MetricAccuracyDetail[] = report?.metric_details ?? [];

  /** The newest run of a company: the place to look when a metric is wrong. */
  const runForTicker = (ticker: string): string =>
    latestRunPerTicker(threads).find((t) => t.ticker === ticker)?.thread_id ?? "/filings";

  const byCompany = useMemo(
    () =>
      Object.entries(report?.by_company ?? {}).map(([ticker, accuracy]) => ({
        ticker,
        label: companyNames[ticker] ?? ticker,
        accuracy,
        thread_id: latestRunPerTicker(threads).find((t) => t.ticker === ticker)?.thread_id,
      })),
    [report, companyNames, threads]
  );

  const calibration = useMemo(
    () =>
      (report?.calibration ?? [])
        .filter((b) => b.count > 0)
        .map((b) => ({
          bucket: `${Math.round(b.lower * 100)}-${Math.round(b.upper * 100)}%`,
          accuracy: b.accuracy,
          count: b.count,
        })),
    [report]
  );

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

  if (error) {
    return (
      <div className="rounded-xl border p-6 text-sm">
        Failed to load accuracy.
        <Button variant="outline" size="sm" className="ml-3">
          Retry
        </Button>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="space-y-4">
        <Card>
          <CardContent className="space-y-2 p-6 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">No verified values yet.</p>
            <p>
              Accuracy is measured against XBRL company facts, so it only exists once a run has been verified.
              Start an audit from <span className="font-medium text-foreground">New audit</span> and this page fills in.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">Final vs XBRL</Badge>
        </div>
        <Button variant="outline" size="sm" onClick={exportCsv} disabled={metricDetails.length === 0}>
          Export CSV
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard title="Final accuracy" value={formatPercent(report.accuracy_pct, 1)} subtitle="Final values vs XBRL" icon={<Crosshair className="h-4 w-4" />} dataTestId="acc-final" />
        <KpiCard title="Original accuracy" value={formatPercent(report.original_accuracy_pct, 1)} subtitle="Pre-human-review values vs XBRL" icon={<Crosshair className="h-4 w-4" />} tone="info" dataTestId="acc-original" />
        <KpiCard title="Auto-approval accuracy" value={formatPercent(report.auto_approval_accuracy_pct, 1)} subtitle={`${report.auto_approved_count} auto-approved`} icon={<Crosshair className="h-4 w-4" />} tone="success" dataTestId="acc-auto" />
        <KpiCard
          title="Escalation precision"
          value={report.escalated_count > 0 ? formatPercent(report.escalation_precision_pct, 1) : "—"}
          subtitle={report.escalated_count > 0 ? `${report.escalated_count} escalated` : "Nothing escalated"}
          icon={<Scale className="h-4 w-4" />}
          tone="warning"
          dataTestId="acc-precision"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Accuracy by company</CardTitle>
          </CardHeader>
          <CardContent>
            {byCompany.length === 0 ? (
              <p className="text-sm text-muted-foreground">No company has verified values yet.</p>
            ) : (
              <div className="h-64 w-full" data-testid="accuracy-by-company-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={byCompany} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="ticker" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} unit="%" />
                    <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                    <Bar
                      dataKey="accuracy"
                      name="Accuracy"
                      fill="hsl(243.2 47.2% 40.4%)"
                      radius={[4, 4, 0, 0]}
                      maxBarSize={64}
                      cursor="pointer"
                      onClick={(entry: { thread_id?: string }) => {
                        if (entry?.thread_id) navigate(`/filings/${entry.thread_id}`);
                      }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Calibration</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 text-sm text-muted-foreground">
              Share of values that match XBRL, bucketed by the confidence the system assigned.
            </p>
            {calibration.length === 0 ? (
              <p className="text-sm text-muted-foreground">No calibration data yet.</p>
            ) : (
              <div className="h-56 w-full" data-testid="calibration-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={calibration} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} unit="%" />
                    <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                    <Line type="monotone" dataKey="accuracy" name="Accuracy" stroke="hsl(243.2 47.2% 40.4%)" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
              {calibration.map((c) => (
                <span key={c.bucket} className="rounded-md border px-2 py-1">
                  {c.bucket} confidence · {c.count} value{c.count === 1 ? "" : "s"} · {c.accuracy.toFixed(0)}% correct
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Per-metric accuracy</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {metricDetails.length === 0 ? (
            <p className="text-sm text-muted-foreground">No verified values yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-medium">Company</th>
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
                  <tr key={`${d.ticker ?? ""}-${d.metric}-${i}`} className="border-b last:border-0">
                    <td className="py-2.5 pr-4 tabular-nums text-muted-foreground">
                      {d.ticker ? (
                        <Link
                          to={`/filings/${runForTicker(d.ticker)}`}
                          className="text-muted-foreground hover:text-foreground hover:underline"
                        >
                          {d.ticker}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
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
          )}
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
                    {Object.entries(report.escalation_precision_by_type ?? {}).map(([type, value]) => (
                      <div key={type} className="flex items-center justify-between text-sm">
                        <span>{type.replace(/_/g, " ")}</span>
                        <span className="tabular-nums">{formatPercent(value, 1)}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Recall</div>
                  <div className="mt-1 text-sm tabular-nums">{formatPercent(report.escalation_recall_pct ?? 0, 1)}</div>
                  <div className="mt-3 text-xs uppercase tracking-wide text-muted-foreground">Values without XBRL truth</div>
                  <div className="mt-1 text-sm tabular-nums">{report.missing_truth?.length ?? 0}</div>
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Gauge as GaugeIcon, ShieldCheck, UserCheck, Bot } from "lucide-react";
import { useThreads, useReport } from "@/hooks/use-trace";
import { StatusBadge } from "@/components/status-badge";
import { KpiCard } from "@/components/kpi-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatPercent, formatDateTime } from "@/lib/format";
import { latestRunPerTicker } from "@/lib/threads";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function OverviewPage() {
  const navigate = useNavigate();
  const { data: threads, isLoading, error } = useThreads();
  const { data: report } = useReport();
  // One run per company: a re-audit must not double every count on this page.
  const threadList = latestRunPerTicker(threads);

  const pending = threadList.filter((t) => t.status === "PAUSED_FOR_REVIEW" || t.status === "HUMAN_REVIEWED");
  const pendingItems = pending.reduce((total, t) => total + (t.flagged_count ?? 0), 0);
  const completed = threadList.filter((t) => t.status === "COMPLETED" || t.status === "AUTO_APPROVED");
  const autoApprovedCount = threadList.reduce((acc, t) => acc + (t.auto_approved_count ?? 0), 0);
  const escalatedCount = threadList.reduce((acc, t) => acc + (t.flagged_count ?? 0), 0);
  const accuracyPct = report?.accuracy_pct ?? null;
  const precisionPct = report && report.escalated_count > 0 ? report.escalation_precision_pct : null;

  const needsAttention = [...pending].sort((a, b) => b.flagged_count - a.flagged_count).slice(0, 5);
  const recent = [...threadList].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 6);

  const chartData = threadList
    .filter((t) => t.status === "COMPLETED" || t.status === "AUTO_APPROVED")
    .map((t) => ({
      ticker: t.ticker,
      thread_id: t.thread_id,
      autoApproved: t.auto_approved_count ?? 0,
      escalated: t.flagged_count ?? 0,
    }));

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-24 animate-pulse rounded-xl border bg-card" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl border bg-card" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !threads) {
    return (
      <div className="rounded-xl border p-6 text-sm">
        Failed to load audits.
        <Button variant="outline" size="sm" className="ml-3">Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard
          title="Pending reviews"
          value={String(pendingItems)}
          subtitle={`${pending.length} run(s) awaiting a reviewer`}
          icon={<UserCheck className="h-4 w-4" />}
          tone="warning"
          dataTestId="kpi-pending"
        />
        <KpiCard title="Completed audits" value={String(completed.length)} subtitle="Across all companies" icon={<CheckCircle2 className="h-4 w-4" />} dataTestId="kpi-completed" />
        <KpiCard title="Auto-approved" value={String(autoApprovedCount)} subtitle="No escalation required" icon={<Bot className="h-4 w-4" />} tone="success" dataTestId="kpi-auto-approved" />
        <KpiCard title="Escalated" value={String(escalatedCount)} subtitle="Flagged for human review" icon={<AlertTriangle className="h-4 w-4" />} tone="danger" dataTestId="kpi-escalated" />
        <KpiCard title="Accuracy" value={formatPercent(accuracyPct, 1)} subtitle="Final vs. XBRL" icon={<GaugeIcon className="h-4 w-4" />} tone="info" dataTestId="kpi-accuracy" />
        <KpiCard title="Escalation precision" value={formatPercent(precisionPct, 1)} subtitle="Escalated items resolved correctly" icon={<ShieldCheck className="h-4 w-4" />} tone="success" dataTestId="kpi-precision" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Needs your attention</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {needsAttention.length === 0 ? (
              <p className="text-sm text-muted-foreground">No pending reviews. All clear.</p>
            ) : (
              needsAttention.map((t) => (
                <Link key={t.thread_id} to={`/review?thread=${t.thread_id}`}>
                  <div className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent/50">
                    <div>
                      <div className="font-medium">{t.company_name} <span className="text-muted-foreground">({t.ticker})</span></div>
                      <div className="text-xs text-muted-foreground">{t.fiscal_year ? `FY${t.fiscal_year}` : "—"} · {t.flagged_count} flagged metric(s)</div>
                    </div>
                    <StatusBadge status={t.status} />
                  </div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Auto-approved vs. escalated</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full" data-testid="auto-vs-escalated-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar
                    dataKey="autoApproved"
                    name="Auto-approved"
                    fill="hsl(142.1 76.2% 36.3%)"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={48}
                    cursor="pointer"
                    onClick={(entry: { thread_id?: string }) => {
                      if (entry?.thread_id) navigate(`/filings/${entry.thread_id}`);
                    }}
                  />
                  <Bar
                    dataKey="escalated"
                    name="Escalated"
                    fill="hsl(0 72% 51%)"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={48}
                    cursor="pointer"
                    onClick={(entry: { thread_id?: string }) => {
                      if (entry?.thread_id) navigate(`/filings/${entry.thread_id}`);
                    }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent filings</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Company</th>
                <th className="py-2 pr-4 font-medium">Ticker</th>
                <th className="py-2 pr-4 font-medium">Fiscal year</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 pr-4 font-medium">Flagged</th>
                <th className="py-2 pr-4 font-medium">Auto-approved</th>
                <th className="py-2 pr-4 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((t) => (
                <tr key={t.thread_id} className="border-b last:border-0 hover:bg-accent/40">
                  <td className="py-2.5 pr-4 font-medium">
                    <Link to={`/filings/${t.thread_id}`} className="text-foreground hover:underline">
                      {t.company_name}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 tabular-nums">{t.ticker}</td>
                  <td className="py-2.5 pr-4 tabular-nums">{t.fiscal_year ?? "—"}</td>
                  <td className="py-2.5 pr-4"><StatusBadge status={t.status} /></td>
                  <td className="py-2.5 pr-4 tabular-nums">{t.flagged_count}</td>
                  <td className="py-2.5 pr-4 tabular-nums">{t.auto_approved_count}</td>
                  <td className="py-2.5 pr-4 text-muted-foreground">{formatDateTime(t.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

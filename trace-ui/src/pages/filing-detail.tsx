import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Copy, Check } from "lucide-react";
import { useThreadStatus, useThreadTimeline } from "@/hooks/use-trace";
import { StatusBadge, ConfidenceBadge, DecisionStateBadge } from "@/components/status-badge";
import { ConfidenceBar } from "@/components/confidence-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatUsdFull, formatUsdCompactPrecise, formatPercent, formatDateTime } from "@/lib/format";
import type { AuditStatusValue } from "@/api/types";

export function FilingDetailPage() {
  const { threadId = "" } = useParams();
  const { data: status, error, isLoading } = useThreadStatus(threadId || null);
  const { data: timeline } = useThreadTimeline(threadId || null);
  const [tab, setTab] = useState("metrics");
  const [expandedMetric, setExpandedMetric] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (isLoading) {
    return <div className="space-y-4">Loading filing…</div>;
  }
  if (error || !status) {
    return <div className="rounded-xl border p-6 text-sm">Failed to load filing. <Button variant="outline" size="sm">Retry</Button></div>;
  }

  const copyThreadId = async () => {
    try {
      await navigator.clipboard.writeText(status.thread_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const accuracy = status.accuracy_report;

  const decisionByMetric = new Map((status.flagged_items ?? []).map((f) => [f.metric_name, f]));
  const validationGroups = new Map<string, typeof status.validation_checks>();
  for (const check of status.validation_checks) {
    const list = validationGroups.get(check.metric_name) ?? [];
    list.push(check);
    validationGroups.set(check.metric_name, list);
  }
  const validationRows = [...validationGroups.entries()];
  const validationCounts = status.validation_checks.reduce(
    (acc, c) => {
      acc[c.status] = (acc[c.status] ?? 0) + 1;
      return acc;
    },
    { PASSED: 0, FAILED: 0, SKIPPED: 0 } as Record<string, number>
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold">{status.company_name}</h2>
                <StatusBadge status={status.status as AuditStatusValue} />
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                Ticker {status.ticker} · CIK {status.cik} · FY{status.fiscal_year} · Period end {status.period_end}
              </div>
              <div className="mt-2 flex items-center gap-2">
                <code className="rounded bg-muted px-2 py-1 text-xs" data-testid="thread-id">{status.thread_id}</code>
                <Button variant="outline" size="sm" onClick={copyThreadId}>
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
                <a className="text-sm text-info hover:underline" href={status.filing_url} target="_blank" rel="noreferrer">
                  View filing ↗
                </a>
              </div>
            </div>
            {status.accuracy_report ? <div className="text-right">Accuracy {formatPercent(status.accuracy_report.accuracy_pct, 1)}</div> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="metrics">Metrics</TabsTrigger>
              <TabsTrigger value="validation">Validation</TabsTrigger>
              <TabsTrigger value="workflow">Workflow</TabsTrigger>
              <TabsTrigger value="accuracy">Accuracy</TabsTrigger>
            </TabsList>

            <TabsContent value="metrics" className="mt-4">
              <div className="space-y-2">
                {(status.metrics ?? []).map((m) => (
                  <div key={m.metric_name} className="rounded-xl border">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-3 p-3 text-left"
                      onClick={() => setExpandedMetric(expandedMetric === m.metric_name ? null : m.metric_name)}
                      aria-expanded={expandedMetric === m.metric_name}
                    >
                      <div>
                        <div className="font-medium">{m.metric_name}</div>
                        <div className="text-xs text-muted-foreground">{m.period}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold tabular-nums">{formatUsdFull(m.value_usd)}</div>
                        <div className="text-xs text-muted-foreground tabular-nums">Compact {formatUsdCompactPrecise(m.value_usd)}</div>
                      </div>
                      <ConfidenceBadge confidence={m.confidence} label={m.confidence_label} />
                      <DecisionStateBadge state={m.decision_state} />
                    </button>
                    {expandedMetric === m.metric_name ? (
                      <div className="border-t p-3 space-y-3">
                        <ConfidenceBar value={m.confidence} label={m.confidence_label} signals={m.confidence_signals} id={m.metric_name} />
                        <div className="font-mono text-xs break-words text-muted-foreground">{m.source_snippet}</div>
                        {m.source_url ? (
                          <a
                            href={m.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-sm text-info hover:underline"
                          >
                            Open this value on SEC.gov ↗
                          </a>
                        ) : null}
                        {m.decision_state !== "FLAGGED" && m.decision_state !== "PENDING" ? (
                          <div className="rounded-lg border border-success/40 bg-success/10 p-3 text-sm">
                            <div className="font-medium text-success">
                              {m.decision_state.toLowerCase()} by {(decisionByMetric.get(m.metric_name)?.reviewer ?? "a reviewer")}
                              {decisionByMetric.get(m.metric_name)?.decided_at ? ` · ${formatDateTime(decisionByMetric.get(m.metric_name)!.decided_at!)}` : ""}
                            </div>
                            {decisionByMetric.get(m.metric_name)?.reviewer_note ? <p className="mt-1 text-muted-foreground">“{decisionByMetric.get(m.metric_name)!.reviewer_note}”</p> : null}
                            {decisionByMetric.get(m.metric_name)?.corrected_value !== null && decisionByMetric.get(m.metric_name)?.corrected_value !== undefined ? (
                              <p className="mt-1 text-muted-foreground">
                                Corrected to {formatUsdFull(decisionByMetric.get(m.metric_name)!.corrected_value!)}
                              </p>
                            ) : null}
                            {(decisionByMetric.get(m.metric_name)?.audit_seq) ? (
                              <Link
                                to={`/audit?thread=${status.thread_id}`}
                                className="mt-1 inline-block text-xs text-info hover:underline"
                              >
                                audit row {decisionByMetric.get(m.metric_name)!.audit_seq} →
                              </Link>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="validation" className="mt-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border p-4">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Passed</div>
                  <div className="mt-1 text-2xl font-semibold text-success">{validationCounts.PASSED ?? 0}</div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Failed</div>
                  <div className="mt-1 text-2xl font-semibold text-danger">{validationCounts.FAILED ?? 0}</div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Skipped</div>
                  <div className="mt-1 text-2xl font-semibold text-muted-foreground">{validationCounts.SKIPPED ?? 0}</div>
                </div>
              </div>
              <div className="mt-4 space-y-2">
                {validationRows.map(([metric, checks]) => (
                  <div key={metric} className="rounded-xl border p-3">
                    <div className="font-medium">{metric}</div>
                    {checks.map((c) => (
                      <div key={c.rule_name} className="mt-1 flex items-center justify-between text-sm">
                        <span className="font-mono text-xs">{c.rule_name}</span>
                        <Badge variant={c.status === "PASSED" ? "success" : c.status === "FAILED" ? "danger" : "muted"}>{c.status}</Badge>
                        <span className="text-muted-foreground">{c.reason}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="workflow" className="mt-4">
              <ol className="relative space-y-4 border-l border-border pl-6">
                {(timeline ?? []).map((e) => (
                  <li key={e.id} className="relative">
                    <span className="absolute -left-[31px] h-2.5 w-2.5 rounded-full bg-info" aria-hidden="true" />
                    <div className="text-sm font-medium">{e.event}</div>
                    <div className="text-xs text-muted-foreground">
                      Step {e.step} · {formatDateTime(e.timestamp)}
                    </div>
                    {e.detail ? <div className="text-xs text-muted-foreground">{e.detail}</div> : null}
                  </li>
                ))}
              </ol>
            </TabsContent>

            <TabsContent value="accuracy" className="mt-4">
              {accuracy ? (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-xl border p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">Accuracy</div>
                      <div className="mt-1 text-2xl font-semibold">{formatPercent(accuracy.accuracy_pct, 1)}</div>
                    </div>
                    <div className="rounded-xl border p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">Original accuracy</div>
                      <div className="mt-1 text-2xl font-semibold">{formatPercent(accuracy.original_accuracy_pct, 1)}</div>
                    </div>
                    <div className="rounded-xl border p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">Escalation precision</div>
                      <div className="mt-1 text-2xl font-semibold">{formatPercent(accuracy.escalation_precision_pct, 1)}</div>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
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
                        {accuracy.metric_details.map((d) => (
                          <tr key={d.metric} className="border-b last:border-0">
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
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Accuracy report not available for this filing.</p>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

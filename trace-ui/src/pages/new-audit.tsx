import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Layers, Search } from "lucide-react";
import { useCompanies, useCompanySearch, useStartAudit, useThreadStatus } from "@/hooks/use-trace";
import type { CompanyInfo } from "@/api/types";
import { Input } from "@/components/ui/input";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function NewAuditPage() {
  const navigate = useNavigate();
  const { data: companies, isLoading } = useCompanies();
  const startAudit = useStartAudit();
  const [query, setQuery] = useState("");
  const search = useCompanySearch(query);
  // Companies added from the SEC search: any ticker, not just the five the demo configures.
  const [extra, setExtra] = useState<CompanyInfo[]>([]);

  const available = useMemo(() => {
    const configured = companies ?? [];
    const known = new Set(configured.map((c) => c.cik));
    return [...configured, ...extra.filter((c) => !known.has(c.cik))];
  }, [companies, extra]);

  const [selected, setSelected] = useState<string[]>(["0000320193"]);
  const [confidence, setConfidence] = useState(0.85);
  const [yoy, setYoY] = useState(0.3);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const activeStatus = useThreadStatus(activeThreadId);

  const runSingle = async (cik: string) => {
    const result = await startAudit.mutateAsync({ cik, confidence_threshold: confidence, yoy_threshold_pct: yoy });
    setActiveThreadId(result.thread_id);
  };

  const runAll = async () => {
    const list = available;
    const targets = list.filter((c) => selected.length === 0 || selected.includes(c.cik));
    const started: string[] = [];
    for (const c of targets) {
      const result = await startAudit.mutateAsync({ cik: c.cik, confidence_threshold: confidence, yoy_threshold_pct: yoy });
      started.push(result.thread_id);
    }
    if (started.length > 0) setActiveThreadId(started[started.length - 1]);
  };

  const toggle = (cik: string) => {
    setSelected((prev) => (prev.includes(cik) ? prev.filter((c) => c !== cik) : [...prev, cik]));
  };

  const threadStatus = activeStatus.data;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>1 · Choose companies</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <div className="h-32 animate-pulse rounded-lg bg-muted" /> : null}
            <div className="relative mb-4">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Audit any company: ticker or name (from SEC EDGAR)"
                aria-label="Search any company on EDGAR"
                className="pl-9"
                data-testid="company-search"
              />
              {query.trim().length >= 2 ? (
                <div className="mt-2 max-h-56 overflow-y-auto rounded-xl border bg-card">
                  {search.isLoading ? (
                    <p className="p-3 text-xs text-muted-foreground">Searching EDGAR…</p>
                  ) : null}
                  {search.isError ? (
                    <p className="p-3 text-xs text-danger">SEC directory unavailable. The five configured companies still work.</p>
                  ) : null}
                  {search.data?.length === 0 && !search.isLoading ? (
                    <p className="p-3 text-xs text-muted-foreground">No company matched “{query.trim()}”.</p>
                  ) : null}
                  {(search.data ?? []).map((c) => {
                    const added = available.some((a) => a.cik === c.cik);
                    return (
                      <button
                        key={c.cik}
                        type="button"
                        disabled={added}
                        onClick={() => {
                          setExtra((prev) => [...prev, c]);
                          setSelected((prev) => (prev.includes(c.cik) ? prev : [...prev, c.cik]));
                          setQuery("");
                        }}
                        className="flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left text-sm last:border-0 hover:bg-accent/50 disabled:opacity-50"
                        data-testid={`company-result-${c.ticker}`}
                      >
                        <span className="truncate">{c.name}</span>
                        <span className="shrink-0 text-xs font-medium text-muted-foreground tabular-nums">
                          {c.ticker} · CIK {c.cik}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {available.map((c) => (
                <button
                  key={c.cik}
                  type="button"
                  onClick={() => toggle(c.cik)}
                  className={cn(
                    "rounded-xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected.includes(c.cik) ? "border-primary bg-accent" : "bg-card hover:bg-accent/50"
                  )}
                  data-testid={`company-card-${c.ticker}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{c.name}</span>
                    <span className="text-sm font-medium text-muted-foreground tabular-nums">{c.ticker}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">CIK {c.cik} · {c.industry}</div>
                </button>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <Button onClick={() => selected.length === 1 && runSingle(selected[0])} disabled={selected.length !== 1 || startAudit.isPending}>
                <Play className="h-4 w-4" aria-hidden="true" />
                Run audit
              </Button>
              <Button variant="outline" onClick={runAll} disabled={startAudit.isPending}>
                <Layers className="h-4 w-4" aria-hidden="true" />
                Run all companies
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>2 · Policy thresholds</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="confidence-threshold">Confidence threshold</Label>
                <span className="rounded-full bg-accent px-2 py-0.5 text-sm font-semibold tabular-nums">{(confidence * 100).toFixed(0)}%</span>
              </div>
              <Slider id="confidence-threshold" min={0.5} max={0.98} step={0.01} value={[confidence]} onValueChange={(v) => setConfidence(v[0])} />
              <p className="mt-1 text-xs text-muted-foreground">Metrics below this confidence escalate for human review.</p>
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="yoy-threshold">YoY change tolerance</Label>
                <span className="rounded-full bg-accent px-2 py-0.5 text-sm font-semibold tabular-nums">{(yoy * 100).toFixed(0)}%</span>
              </div>
              <Slider id="yoy-threshold" min={0} max={0.8} step={0.01} value={[yoy]} onValueChange={(v) => setYoY(v[0])} />
              <p className="mt-1 text-xs text-muted-foreground">Larger year-over-year deviations escalate for financial anomaly review.</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {activeThreadId ? (
        <Card>
          <CardHeader>
            <CardTitle>Run status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              {threadStatus ? <StatusBadge status={threadStatus.status} /> : <Badge variant="secondary">Starting…</Badge>}
            </div>
            <WorkflowStepper status={threadStatus?.status ?? "STARTED"} />
            {threadStatus?.status === "PAUSED_FOR_REVIEW" ? (
              <div className="flex items-center gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4">
                <Badge variant="warning">Paused at checkpoint</Badge>
                <span className="text-sm">This audit is waiting for human decisions.</span>
                <Button size="sm" className="ml-auto" onClick={() => navigate(`/review?thread=${activeThreadId}`)}>
                  Open review queue
                </Button>
              </div>
            ) : null}
            {threadStatus?.status === "FAILED" ? (
              <div className="rounded-xl border border-danger/40 bg-danger/10 p-4 text-sm text-danger">This audit failed. Check the simulate-failure toggle in Settings.</div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <p className="text-xs text-muted-foreground">Live 9-step workflow · Filing retrieval → Extraction → Confidence scoring → Validation → Automated decision → Human review → Decision and resume → XBRL verification → Audit history</p>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ExternalLink, ShieldAlert } from "lucide-react";
import { useThreads, useThreadStatus, useResume } from "@/hooks/use-trace";
import { DecisionStateBadge, ConfidenceBadge, EscalationBadge, TierBadge } from "@/components/status-badge";
import { ConfidenceBar } from "@/components/confidence-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { formatUsdFull, formatUsdCompactPrecise, formatDateTime } from "@/lib/format";
import { latestRunPerTicker } from "@/lib/threads";
import type { FlaggedItem, ResumePayload, ValidationCheck } from "@/api/types";
import { toast } from "sonner";

type FilterTab = "PENDING" | "DECIDED" | "ALL";

interface LocalDecision {
  decision: "APPROVED" | "CORRECTED" | "REJECTED";
  corrected_value?: number;
  reviewer_notes?: string;
}

/** Identity of a flagged row. review_id is per metric and survives re-renders; metric_name does
 * not, because one metric can carry several escalations (extraction risk + failed validation). */
export function flagKey(item: FlaggedItem): string {
  return item.review_id ?? item.metric_name;
}

/** Critical first: the tier is decided by the server, the UI only orders by it. */
function tierRank(item: FlaggedItem): number {
  return item.tier === "red" ? 0 : item.tier === "yellow" ? 1 : 2;
}

/**
 * Highlight the exact text the extractor matched inside the filing snippet.
 * The server sends matched_text (a literal substring); if it is missing we fall back to
 * highlighting the money amounts, which is the best guess we can honestly make.
 */
function highlightSnippet(snippet: string, matched?: string) {
  if (matched && matched.length > 0 && snippet.includes(matched)) {
    const parts = snippet.split(matched);
    return parts.map((part, index) => (
      <span key={index}>
        {part}
        {index < parts.length - 1 ? (
          <mark className="rounded bg-warning/30 px-0.5 text-warning-foreground" data-testid="matched-text">
            {matched}
          </mark>
        ) : null}
      </span>
    ));
  }
  return snippet.split(/(\$[\d.,]+[A-Za-z]*)/).map((part, i) =>
    /^\$[\d.,]+[A-Za-z]*$/.test(part) ? (
      <mark key={i} className="rounded bg-warning/30 px-0.5 text-warning-foreground">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export function ReviewQueuePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const threadIdParam = searchParams.get("thread");
  const { data: threads } = useThreads();
  // One pending run per company, newest first: an older run of the same company must not
  // take over the queue.
  const pendingThreads = latestRunPerTicker(threads).filter((t) => t.status === "PAUSED_FOR_REVIEW" || t.status === "HUMAN_REVIEWED");
  // Nothing pending: fall back to the newest run so the decided items stay visible.
  const fallbackThread = latestRunPerTicker(threads)[0] ?? null;

  const threadId =
    threadIdParam && (threads ?? []).some((t) => t.thread_id === threadIdParam)
      ? threadIdParam
      : (pendingThreads[0]?.thread_id ?? fallbackThread?.thread_id ?? null);

  const { data: status, error, isLoading } = useThreadStatus(threadId);
  const resume = useResume();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, LocalDecision>>({});
  const [filter, setFilter] = useState<FilterTab>("PENDING");
  const [bulkOpen, setBulkOpen] = useState(false);

  const flagged = useMemo(() => {
    // Defensive: never render two rows for one metric id, even if an older API build returns
    // rows from several runs of the same company. Pending rows win when both are present.
    const rows = [...(status?.flagged_items ?? [])].sort((a, b) => {
      if (a.decision_state === "FLAGGED" && b.decision_state !== "FLAGGED") return -1;
      if (b.decision_state === "FLAGGED" && a.decision_state !== "FLAGGED") return 1;
      return tierRank(a) - tierRank(b);
    });
    const seen = new Set<string>();
    return rows.filter((f) => {
      const key = flagKey(f);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [status]);
  const pendingItems = flagged.filter((f) => f.decision_state === "FLAGGED");
  const decidedItems = flagged.filter((f) => f.decision_state !== "FLAGGED");
  const visibleItems = filter === "PENDING" ? pendingItems : filter === "DECIDED" ? decidedItems : flagged;

  const selectedFlagged: FlaggedItem | null = useMemo(
    () => flagged.find((f) => flagKey(f) === selectedKey) ?? null,
    [flagged, selectedKey]
  );

  const reviewedCount = flagged.filter((f) => decisions[flagKey(f)] !== undefined).length;
  const decidedPendingCount = pendingItems.filter((f) => decisions[flagKey(f)] !== undefined).length;
  const progressPct = flagged.length > 0 ? Math.round((reviewedCount / flagged.length) * 100) : 0;

  const submit = async (override?: Record<string, LocalDecision>) => {
    if (!threadId) return;
    const decided = override ?? decisions;
    const payload: ResumePayload = {
      decisions: pendingItems
        .map((f) => ({ flagged: f, decision: decided[flagKey(f)] }))
        .filter((x) => x.decision)
        .map((x) => ({
          metric_name: x.flagged.metric_name,
          decision: x.decision!.decision,
          corrected_value: x.decision!.corrected_value,
          reviewer_notes: x.decision!.reviewer_notes,
        })),
    };
    if (payload.decisions.length === 0) {
      toast.error("Nothing to submit");
      return;
    }
    await resume.mutateAsync({ threadId, payload });
    setDecisions({});
    setSelectedKey(null);
    toast.success(`Recorded ${payload.decisions.length} decision(s) in the audit log`, {
      action: {
        label: "Show the log",
        onClick: () => navigate(`/audit?thread=${threadId}`),
      },
    });
  };

  const approveAll = (items: FlaggedItem[]): Record<string, LocalDecision> => {
    const next: Record<string, LocalDecision> = {};
    for (const f of items) {
      next[flagKey(f)] = { decision: "APPROVED", reviewer_notes: "Bulk approved from review queue" };
    }
    setDecisions(next);
    return next;
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      if (event.key === "j" || event.key === "J") {
        const idx = visibleItems.findIndex((f) => flagKey(f) === selectedKey);
        const next = visibleItems[(idx + 1) % Math.max(1, visibleItems.length)];
        if (next) setSelectedKey(flagKey(next));
      }
      if (event.key === "k" || event.key === "K") {
        const idx = visibleItems.findIndex((f) => flagKey(f) === selectedKey);
        const prev = visibleItems[(idx - 1 + Math.max(1, visibleItems.length)) % Math.max(1, visibleItems.length)];
        if (prev) setSelectedKey(flagKey(prev));
      }
      if (event.key === "a" || event.key === "A") {
        const targetItem = selectedFlagged ?? visibleItems.find((f) => f.decision_state === "FLAGGED");
        if (targetItem) {
          setDecisions((prev) => ({ ...prev, [flagKey(targetItem)]: { decision: "APPROVED", reviewer_notes: "Approved via keyboard shortcut" } }));
        }
      }
      if (event.key === "c" || event.key === "C") {
        const targetItem = selectedFlagged ?? visibleItems.find((f) => f.decision_state === "FLAGGED");
        if (targetItem) {
          setDecisions((prev) => ({ ...prev, [flagKey(targetItem)]: { decision: "CORRECTED" } }));
        }
      }
      if (event.key === "r" || event.key === "R") {
        const targetItem = selectedFlagged ?? visibleItems.find((f) => f.decision_state === "FLAGGED");
        if (targetItem) {
          setDecisions((prev) => ({ ...prev, [flagKey(targetItem)]: { decision: "REJECTED", reviewer_notes: "Rejected via keyboard shortcut" } }));
        }
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        void submit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (isLoading) {
    return <div className="space-y-4">Loading review queue…</div>;
  }
  if (error) {
    return (
      <div className="rounded-xl border p-6 text-sm">
        Failed to load the review queue. <Button variant="outline" size="sm">Retry</Button>
      </div>
    );
  }
  if (!status) {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border p-6 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Nothing is waiting for a reviewer.</p>
          <p className="mt-1">
            Every flagged value has been decided. Start a new audit from{" "}
            <span className="font-medium text-foreground">New audit</span> to open a new queue.
          </p>
        </div>
      </div>
    );
  }

  const selectedDecision = selectedFlagged ? decisions[flagKey(selectedFlagged)] : undefined;

  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100vh-11rem)] lg:min-h-[520px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge variant="warning">{pendingItems.length} pending</Badge>
          {status?.company_name ? (
            <span className="text-sm text-muted-foreground">
              {status.company_name} ({status.ticker}) · {status.period_end || `FY${status.fiscal_year}`}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setBulkOpen(true)} disabled={pendingItems.length === 0}>
            Bulk approve
          </Button>
          <Button size="sm" onClick={() => void submit()} disabled={resume.isPending || decidedPendingCount === 0}>
            Submit decisions ({decidedPendingCount})
          </Button>
        </div>
      </div>

      {pendingThreads.length > 1 ? (
        <div className="flex flex-wrap gap-2">
          {pendingThreads.map((t) => (
            <button
              key={t.thread_id}
              type="button"
              onClick={() => setSearchParams({ thread: t.thread_id })}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                t.thread_id === threadId ? "border-primary bg-accent text-accent-foreground" : "bg-card hover:bg-accent/60"
              }`}
              data-testid={`queue-company-${t.ticker}`}
            >
              {t.ticker} · {t.flagged_count} flagged
            </button>
          ))}
        </div>
      ) : null}

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Progress · {reviewedCount} of {flagged.length} reviewed
          </span>
          <span>{progressPct}%</span>
        </div>
        <Progress value={progressPct} />
      </div>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-5 lg:overflow-hidden">
        <Card className="flex min-h-0 flex-col lg:col-span-2 lg:overflow-hidden">
          <CardHeader className="shrink-0 pb-3">
            <Tabs value={filter} onValueChange={(v) => setFilter(v as FilterTab)}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="PENDING">Pending</TabsTrigger>
                <TabsTrigger value="DECIDED">Decided</TabsTrigger>
                <TabsTrigger value="ALL">All</TabsTrigger>
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
            {visibleItems.length === 0 ? <p className="text-sm text-muted-foreground">No items in this view.</p> : null}
            {visibleItems.map((f) => (
              <button
                key={flagKey(f)}
                type="button"
                onClick={() => setSelectedKey(flagKey(f))}
                className={`rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  selectedKey === flagKey(f) ? "border-primary bg-accent" : "bg-card hover:bg-accent/50"
                }`}
                data-testid={`queue-item-${f.metric_name}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{f.metric_name}</span>
                  <ConfidenceBadge confidence={f.confidence} label={f.confidence_label} />
                </div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{formatUsdFull(f.value_usd)}</div>
                <div className="mt-2 flex items-center gap-2">
                  <TierBadge tier={f.tier} />
                  {f.escalation_types.map((t) => (
                    <EscalationBadge key={t} type={t} />
                  ))}
                  <DecisionStateBadge state={f.decision_state} />
                </div>
                {f.decision_state !== "FLAGGED" && f.reviewer ? (
                  <div className="mt-1 text-xs text-muted-foreground">
                    {f.decision_state.toLowerCase()} by {f.reviewer}
                    {f.decided_at ? ` · ${formatDateTime(f.decided_at)}` : ""}
                    {f.reviewer_note ? ` — “${f.reviewer_note}”` : ""}
                    {f.audit_seq ? (
                      <>
                        {" "}
                        <Link
                          to={`/audit?thread=${threadId ?? ""}`}
                          className="text-info hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          audit row {f.audit_seq}
                        </Link>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="hidden min-h-0 flex-col lg:col-span-3 lg:flex lg:overflow-hidden">
          {selectedFlagged ? (
            <ItemDetail
              key={flagKey(selectedFlagged)}
              flagged={selectedFlagged}
              checks={status.validation_checks.filter(
                (v) => v.status === "FAILED" && v.metrics_involved.includes(selectedFlagged.metric_name)
              )}
              threadId={threadId}
              decision={selectedDecision}
              onDecisionChange={(d) => setDecisions((prev) => ({ ...prev, [flagKey(selectedFlagged)]: d }))}
            />
          ) : (
            <CardContent className="flex min-h-0 flex-1 flex-col items-center justify-center text-center">
              <ShieldAlert className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
              <h3 className="mt-3 font-semibold">Select a flagged item</h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">Pick an item on the left to inspect the evidence and record a decision.</p>
            </CardContent>
          )}
        </Card>
      </div>

      {/* On a phone the detail is a full-screen sheet: the two-column layout does not fit. */}
      {selectedFlagged ? (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-background p-4 lg:hidden" data-testid="queue-detail-sheet">
          <div className="mb-3 flex items-center justify-between">
            <Button variant="outline" size="sm" onClick={() => setSelectedKey(null)}>
              ← Back to the queue
            </Button>
            <span className="text-xs text-muted-foreground">{status.company_name}</span>
          </div>
          <ItemDetail
            key={flagKey(selectedFlagged)}
            flagged={selectedFlagged}
            checks={status.validation_checks.filter(
              (v) => v.status === "FAILED" && v.metrics_involved.includes(selectedFlagged.metric_name)
            )}
            threadId={threadId}
            decision={selectedDecision}
            onDecisionChange={(d) => setDecisions((prev) => ({ ...prev, [flagKey(selectedFlagged)]: d }))}
          />
        </div>
      ) : null}

      <div className="rounded-xl border bg-card p-3 text-xs text-muted-foreground">
        Shortcuts: <kbd className="rounded border bg-muted px-1">J</kbd>/<kbd className="rounded border bg-muted px-1">K</kbd> navigate · <kbd className="rounded border bg-muted px-1">A</kbd> approve · <kbd className="rounded border bg-muted px-1">C</kbd> correct · <kbd className="rounded border bg-muted px-1">R</kbd> reject · <kbd className="rounded border bg-muted px-1">⌘/Ctrl</kbd>+<kbd className="rounded border bg-muted px-1">Enter</kbd> submit
      </div>

      <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bulk approve</DialogTitle>
            <DialogDescription>This will submit APPROVED decisions for every pending flagged item.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                // The map is passed on: React state is not updated yet inside this handler.
                const next = approveAll(pendingItems);
                setBulkOpen(false);
                void submit(next);
              }}
            >
              Approve {pendingItems.length}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ItemDetail({
  flagged,
  checks,
  threadId,
  decision,
  onDecisionChange,
}: {
  flagged: FlaggedItem;
  checks: ValidationCheck[];
  threadId: string | null;
  decision?: LocalDecision;
  onDecisionChange: (d: LocalDecision) => void;
}) {
  const [correctedValue, setCorrectedValue] = useState<string>(String(flagged.value_usd));
  const [note, setNote] = useState("");

  const isPending = flagged.decision_state === "FLAGGED";

  const applyDecision = (d: LocalDecision) => {
    const next = { ...d, reviewer_notes: note || d.reviewer_notes };
    if (d.decision === "CORRECTED") next.corrected_value = Number(correctedValue) || flagged.value_usd;
    onDecisionChange(next);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <CardHeader className="flex items-start justify-between space-y-0">
        <div>
          <div className="flex items-center gap-2">
            <CardTitle className="text-xl">{flagged.metric_name}</CardTitle>
            <TierBadge tier={flagged.tier} />
            <DecisionStateBadge state={flagged.decision_state} />
          </div>
          <div className="mt-1 text-sm text-muted-foreground">
            Period {flagged.period} · Reported unit {flagged.unit} · Prior year{" "}
            {flagged.prior_year_value_usd === null ? "—" : formatUsdFull(flagged.prior_year_value_usd)}
          </div>
        </div>
        <div className="text-right">
          <div className="font-sans text-2xl font-semibold tabular-nums">{formatUsdFull(flagged.value_usd)}</div>
          <div className="text-xs text-muted-foreground tabular-nums">Full USD · {flagged.unit}</div>
          <div className="text-xs text-muted-foreground tabular-nums">Compact {formatUsdCompactPrecise(flagged.value_usd)}</div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 space-y-5 overflow-y-auto">
        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">Confidence</h4>
          <div className="mt-3">
            <ConfidenceBar value={flagged.confidence} label={flagged.confidence_label} signals={flagged.confidence_signals} id={flagged.metric_name} />
          </div>
          <div className="mt-3">
            <ConfidenceBadge confidence={flagged.confidence} label={flagged.confidence_label} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Confidence measures how cleanly the number was read from the filing - not whether it is right.
            A clean read can still be the wrong line, which is why validation still escalates it.
          </p>
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">Why this was escalated</h4>
          <ul className="mt-2 space-y-1">
            {flagged.reasons.map((r) => (
              <li key={r} className="flex items-start gap-2 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
          <div className="mt-2 flex gap-2">
            {flagged.escalation_types.map((t) => (
              <EscalationBadge key={t} type={t} />
            ))}
          </div>
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">Source evidence</h4>
          <div className="mt-2 rounded-lg border bg-muted/40 p-3">
            <div className="font-mono text-xs text-muted-foreground">{flagged.source_header}</div>
            <div className="mt-1 font-mono text-sm break-words whitespace-pre-wrap" data-testid="source-snippet">
              {highlightSnippet(flagged.source_snippet, flagged.matched_text)}
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            {flagged.source_url ? (
              <a
                className="inline-flex items-center gap-1 text-sm text-info hover:underline"
                href={flagged.source_url}
                target="_blank"
                rel="noreferrer"
                data-testid="source-link"
              >
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                Open this value on SEC.gov
              </a>
            ) : null}
            {threadId ? (
              <Link
                to={`/filings/${threadId}`}
                className="inline-flex items-center gap-1 text-sm text-info hover:underline"
                data-testid="run-link"
              >
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                Open the run detail
              </Link>
            ) : null}
          </div>
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">Validation checks</h4>
          {checks.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              No failed validation rule names this metric. It was flagged by a confidence or extraction rule.
            </p>
          ) : (
            <ul className="mt-2 space-y-2">
              {checks.map((check) => (
                <li key={check.rule_name + check.metric_name} className="rounded-lg border bg-danger/5 p-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{check.rule_name}</span>
                    <span className="text-xs uppercase tracking-wide text-danger">Failed</span>
                  </div>
                  <p className="mt-1 text-muted-foreground">{check.reason}</p>
                  {check.details && check.details !== check.reason ? (
                    <p className="mt-1 font-mono text-xs text-muted-foreground">{check.details}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">AI-generated explanation</h4>
          <p className="mt-2 text-sm text-muted-foreground">
            AI-generated, unverified. This summary was produced by the model layer and has not been independently validated. Human judgment required.
          </p>
        </section>
      </CardContent>

      <div className="border-t bg-card p-3">
        <section>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <h4 className="text-sm font-semibold">Decision</h4>
              {!isPending && flagged.reviewer ? (
                <div className="mt-2 rounded-lg border border-success/40 bg-success/10 p-3 text-sm">
                  <div className="font-medium text-success">
                    {flagged.decision_state.toLowerCase()} by {flagged.reviewer}
                    {flagged.decided_at ? ` · ${formatDateTime(flagged.decided_at)}` : ""}
                  </div>
                  {flagged.reviewer_note ? (
                    <p className="mt-1 text-muted-foreground">“{flagged.reviewer_note}”</p>
                  ) : null}
                  {flagged.corrected_value !== null && flagged.corrected_value !== undefined ? (
                    <p className="mt-1 text-muted-foreground">
                      Corrected to {formatUsdFull(flagged.corrected_value)}
                    </p>
                  ) : null}
                  {flagged.audit_seq && threadId ? (
                    <Link
                      to={`/audit?thread=${threadId}`}
                      className="mt-1 inline-block text-xs text-info hover:underline"
                    >
                      audit row {flagged.audit_seq} →
                    </Link>
                  ) : null}
                </div>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant={decision?.decision === "APPROVED" ? "default" : "outline"}
                  onClick={() => applyDecision({ decision: "APPROVED" })}
                  disabled={!isPending || note.trim().length === 0}
                  title={note.trim().length === 0 ? "Write a note before approving" : undefined}
                >
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Approve
                </Button>
                <Button size="sm" variant={decision?.decision === "CORRECTED" ? "default" : "outline"} onClick={() => applyDecision({ decision: "CORRECTED" })} disabled={!isPending}>
                  Correct
                </Button>
                <Button size="sm" variant={decision?.decision === "REJECTED" ? "default" : "outline"} onClick={() => applyDecision({ decision: "REJECTED" })} disabled={!isPending}>
                  Reject
                </Button>
              </div>
            </div>
            {isPending ? (
              <div className="min-w-[220px] flex-1 space-y-1">
                <label className="text-xs font-medium text-muted-foreground" htmlFor={`note-${flagged.metric_name}`}>
                  Reviewer note (required to approve)
                </label>
                <Textarea
                  id={`note-${flagged.metric_name}`}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="What did you check against the filing?"
                  rows={2}
                  className="min-h-[44px]"
                />
              </div>
            ) : null}
          </div>
          {isPending && decision?.decision === "CORRECTED" ? (
            <div className="mt-2 max-w-xs">
              <label className="text-xs font-medium text-muted-foreground" htmlFor={`corrected-${flagged.metric_name}`}>
                Corrected value ({flagged.unit})
              </label>
              <Input id={`corrected-${flagged.metric_name}`} type="number" step="any" value={correctedValue} onChange={(e) => setCorrectedValue(e.target.value)} />
            </div>
          ) : null}
          {isPending && note.trim().length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Approve stays disabled until you write a note. Every decision is recorded in the audit log.
            </p>
          ) : null}
        </section>
      </div>
    </div>
  );
}

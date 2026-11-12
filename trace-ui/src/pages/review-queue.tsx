import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ExternalLink, ShieldAlert } from "lucide-react";
import { useThreads, useThreadStatus, useResume } from "@/hooks/use-trace";
import { DecisionStateBadge, ConfidenceBadge, EscalationBadge } from "@/components/status-badge";
import { ConfidenceBar } from "@/components/confidence-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { formatUsdFull, formatUsdCompactPrecise } from "@/lib/format";
import type { FlaggedItem, ResumePayload } from "@/api/types";
import { toast } from "sonner";

type FilterTab = "PENDING" | "DECIDED" | "ALL";

interface LocalDecision {
  decision: "APPROVED" | "CORRECTED" | "REJECTED";
  corrected_value?: number;
  reviewer_notes?: string;
}

export function ReviewQueuePage() {
  const [searchParams] = useSearchParams();
  const threadIdParam = searchParams.get("thread");
  const { data: threads } = useThreads();
  const pendingThreads = (threads ?? []).filter((t) => t.status === "PAUSED_FOR_REVIEW" || t.status === "HUMAN_REVIEWED");

  const threadId =
    threadIdParam && (threads ?? []).some((t) => t.thread_id === threadIdParam)
      ? threadIdParam
      : (pendingThreads[0]?.thread_id ?? null);

  const { data: status, error, isLoading } = useThreadStatus(threadId);
  const resume = useResume();
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, LocalDecision>>({});
  const [filter, setFilter] = useState<FilterTab>("PENDING");
  const [bulkOpen, setBulkOpen] = useState(false);

  const flagged = status?.flagged_items ?? [];
  const pendingItems = flagged.filter((f) => f.decision_state === "FLAGGED");
  const decidedItems = flagged.filter((f) => f.decision_state !== "FLAGGED");
  const visibleItems = filter === "PENDING" ? pendingItems : filter === "DECIDED" ? decidedItems : flagged;

  const selectedFlagged: FlaggedItem | null = useMemo(
    () => flagged.find((f) => f.metric_name === selectedMetric) ?? null,
    [flagged, selectedMetric]
  );

  const reviewedCount = flagged.filter((f) => decisions[f.metric_name] !== undefined).length;
  const progressPct = flagged.length > 0 ? Math.round((reviewedCount / flagged.length) * 100) : 0;

  const submit = async () => {
    if (!threadId) return;
    const payload: ResumePayload = {
      decisions: pendingItems
        .map((f) => ({ flagged: f, decision: decisions[f.metric_name] }))
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
    const result = await resume.mutateAsync({ threadId, payload });
    setDecisions({});
    setSelectedMetric(null);
    toast.success(`Submitted ${payload.decisions.length} decision(s) — audit ${result.status}`);
  };

  const approveAll = (items: FlaggedItem[]) => {
    const next: Record<string, LocalDecision> = {};
    for (const f of items) {
      next[f.metric_name] = { decision: "APPROVED", reviewer_notes: "Bulk approved from review queue" };
    }
    setDecisions(next);
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      if (event.key === "j" || event.key === "J") {
        const idx = visibleItems.findIndex((f) => f.metric_name === selectedMetric);
        const next = visibleItems[(idx + 1) % Math.max(1, visibleItems.length)];
        if (next) setSelectedMetric(next.metric_name);
      }
      if (event.key === "k" || event.key === "K") {
        const idx = visibleItems.findIndex((f) => f.metric_name === selectedMetric);
        const prev = visibleItems[(idx - 1 + Math.max(1, visibleItems.length)) % Math.max(1, visibleItems.length)];
        if (prev) setSelectedMetric(prev.metric_name);
      }
      if (event.key === "a" || event.key === "A") {
        const targetItem = selectedFlagged ?? visibleItems.find((f) => f.decision_state === "FLAGGED");
        if (targetItem) {
          setDecisions((prev) => ({ ...prev, [targetItem.metric_name]: { decision: "APPROVED", reviewer_notes: "Approved via keyboard shortcut" } }));
        }
      }
      if (event.key === "c" || event.key === "C") {
        const targetItem = selectedFlagged ?? visibleItems.find((f) => f.decision_state === "FLAGGED");
        if (targetItem) {
          setDecisions((prev) => ({ ...prev, [targetItem.metric_name]: { decision: "CORRECTED" } }));
        }
      }
      if (event.key === "r" || event.key === "R") {
        const targetItem = selectedFlagged ?? visibleItems.find((f) => f.decision_state === "FLAGGED");
        if (targetItem) {
          setDecisions((prev) => ({ ...prev, [targetItem.metric_name]: { decision: "REJECTED", reviewer_notes: "Rejected via keyboard shortcut" } }));
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
  if (error || !status) {
    return <div className="rounded-xl border p-6 text-sm">Failed to load review queue. <Button variant="outline" size="sm">Retry</Button></div>;
  }

  const selectedDecision = selectedFlagged ? decisions[selectedFlagged.metric_name] : undefined;

  return (
    <div className="flex h-[calc(100vh-12rem)] min-h-[560px] flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Review queue</h2>
          <Badge variant="warning">{pendingItems.length} pending</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setBulkOpen(true)} disabled={pendingItems.length === 0}>
            Bulk approve
          </Button>
          <Button size="sm" onClick={() => void submit()} disabled={resume.isPending || pendingItems.length === 0 || pendingItems.some((f) => !decisions[f.metric_name])}>
            Submit decisions ({pendingItems.length})
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Progress · {reviewedCount} of {flagged.length} reviewed
          </span>
          <span>{progressPct}%</span>
        </div>
        <Progress value={progressPct} />
      </div>

      <div className="grid flex-1 gap-4 overflow-hidden lg:grid-cols-5">
        <Card className="lg:col-span-2 lg:overflow-hidden">
          <CardHeader className="pb-3">
            <Tabs value={filter} onValueChange={(v) => setFilter(v as FilterTab)}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="PENDING">Pending</TabsTrigger>
                <TabsTrigger value="DECIDED">Decided</TabsTrigger>
                <TabsTrigger value="ALL">All</TabsTrigger>
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 overflow-y-auto">
            {visibleItems.length === 0 ? <p className="text-sm text-muted-foreground">No items in this view.</p> : null}
            {visibleItems.map((f) => (
              <button
                key={f.metric_name}
                type="button"
                onClick={() => setSelectedMetric(f.metric_name)}
                className={`rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  selectedMetric === f.metric_name ? "border-primary bg-accent" : "bg-card hover:bg-accent/50"
                }`}
                data-testid={`queue-item-${f.metric_name}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{f.metric_name}</span>
                  <ConfidenceBadge confidence={f.confidence} label={f.confidence_label} />
                </div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{formatUsdFull(f.value_usd)}</div>
                <div className="mt-2 flex items-center gap-2">
                  {f.escalation_types.map((t) => (
                    <EscalationBadge key={t} type={t} />
                  ))}
                  <DecisionStateBadge state={f.decision_state} />
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3 lg:overflow-hidden">
          {selectedFlagged ? (
            <ItemDetail
              flagged={selectedFlagged}
              decision={selectedDecision}
              onDecisionChange={(d) => setDecisions((prev) => ({ ...prev, [selectedFlagged.metric_name]: d }))}
            />
          ) : (
            <CardContent className="flex h-full flex-col items-center justify-center text-center">
              <ShieldAlert className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
              <h3 className="mt-3 font-semibold">Select a flagged item</h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">Pick an item on the left to inspect the evidence and record a decision.</p>
            </CardContent>
          )}
        </Card>
      </div>

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
                approveAll(pendingItems);
                setBulkOpen(false);
                void submit();
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
  decision,
  onDecisionChange,
}: {
  flagged: FlaggedItem;
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
    <div className="flex h-full flex-col overflow-y-auto">
      <CardHeader className="flex items-start justify-between space-y-0">
        <div>
          <div className="flex items-center gap-2">
            <CardTitle className="text-xl">{flagged.metric_name}</CardTitle>
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
      <CardContent className="space-y-5">
        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">Confidence</h4>
          <div className="mt-3">
            <ConfidenceBar value={flagged.confidence} label={flagged.confidence_label} signals={flagged.confidence_signals} id={flagged.metric_name} />
          </div>
          <div className="mt-3">
            <ConfidenceBadge confidence={flagged.confidence} label={flagged.confidence_label} />
          </div>
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
              {flagged.source_snippet.split(/(\$[\d.,]+[A-Za-z]*)/).map((part, i) =>
                /^\$[\d.,]+[A-Za-z]*$/.test(part) ? <mark key={i} className="rounded bg-warning/30 px-0.5 text-warning-foreground">{part}</mark> : <span key={i}>{part}</span>
              )}
            </div>
          </div>
          <a className="mt-2 inline-flex items-center gap-1 text-sm text-info hover:underline" href={`#filing-${flagged.metric_name}`}>
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            View source in filing
          </a>
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">Validation checks</h4>
          <div className="mt-2 space-y-2">
            {flagged && <div className="text-xs text-muted-foreground">Per-metric validation detail is available on the filing detail page.</div>}
          </div>
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">AI-generated explanation</h4>
          <p className="mt-2 text-sm text-muted-foreground">
            AI-generated, unverified. This summary was produced by the model layer and has not been independently validated. Human judgment required.
          </p>
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="text-sm font-semibold">Decision</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" variant={decision?.decision === "APPROVED" ? "default" : "outline"} onClick={() => applyDecision({ decision: "APPROVED" })} disabled={!isPending}>
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Approve
            </Button>
            <Button size="sm" variant={decision?.decision === "CORRECTED" ? "default" : "outline"} onClick={() => applyDecision({ decision: "CORRECTED" })} disabled={!isPending}>
              Correct
            </Button>
            <Button size="sm" variant={decision?.decision === "REJECTED" ? "default" : "outline"} onClick={() => applyDecision({ decision: "REJECTED" })} disabled={!isPending}>
              Reject
            </Button>
          </div>
          {isPending ? (
            <div className="mt-3 space-y-2">
              {decision?.decision === "CORRECTED" ? (
                <div>
                  <label className="text-xs font-medium text-muted-foreground" htmlFor={`corrected-${flagged.metric_name}`}>
                    Corrected value ({flagged.unit})
                  </label>
                  <Input id={`corrected-${flagged.metric_name}`} type="number" step="any" value={correctedValue} onChange={(e) => setCorrectedValue(e.target.value)} />
                </div>
              ) : null}
              <div>
                <label className="text-xs font-medium text-muted-foreground" htmlFor={`note-${flagged.metric_name}`}>
                  Reviewer note
                </label>
                <Textarea id={`note-${flagged.metric_name}`} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional rationale" />
              </div>
            </div>
          ) : null}
        </section>
      </CardContent>
    </div>
  );
}

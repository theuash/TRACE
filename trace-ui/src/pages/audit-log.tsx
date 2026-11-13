import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ShieldCheck, ShieldAlert, Lock, Download } from "lucide-react";
import { useAuditLogs, useVerifyChain } from "@/hooks/use-trace";
import { DecisionBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatDateTime, formatUsdFull } from "@/lib/format";
import type { AuditLogRow } from "@/api/types";

const decisions = ["ALL", "AUTO_APPROVED", "APPROVED", "CORRECTED", "REJECTED"] as const;

export function AuditLogPage() {
  const [decisionFilter, setDecisionFilter] = useState<(typeof decisions)[number]>("ALL");
  const [query, setQuery] = useState("");
  const [selectedRow, setSelectedRow] = useState<AuditLogRow | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const threadFilter = searchParams.get("thread");

  const filters = useMemo(
    () => ({
      decision: decisionFilter === "ALL" ? undefined : decisionFilter,
      thread_id: threadFilter ?? undefined,
    }),
    [decisionFilter, threadFilter]
  );
  const { data: rows, isLoading, error } = useAuditLogs(filters);
  const { data: verification, refetch: refetchVerification } = useVerifyChain();

  const visibleRows = (rows ?? []).filter(
    (r) =>
      !query ||
      r.company_name.toLowerCase().includes(query.toLowerCase()) ||
      r.metric_name.toLowerCase().includes(query.toLowerCase()) ||
      r.thread_id.toLowerCase().includes(query.toLowerCase())
  );

  const exportCsv = () => {
    const header = ["id", "timestamp", "company", "metric", "decision", "original_value", "corrected_value", "reviewer_notes", "prev_hash", "row_hash"];
    const lines = visibleRows.map((r) =>
      [r.id, r.timestamp, r.company_name, r.metric_name, r.decision, String(r.original_value), String(r.corrected_value ?? ""), r.reviewer_notes, r.prev_hash, r.row_hash].join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trace-audit-log.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="gap-1">
            <Lock className="h-3 w-3" aria-hidden="true" /> Append-only
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void refetchVerification()}>
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Verify chain
          </Button>
          <Button variant="outline" size="sm" onClick={exportCsv} disabled={(rows ?? []).length === 0}>
            <Download className="h-4 w-4" aria-hidden="true" />
            Export CSV
          </Button>
        </div>
      </div>

          {verification ? (
            <div
              className={`rounded-xl border p-4 text-sm ${verification.verified ? "border-success/40 bg-success/10 text-success" : "border-danger/40 bg-danger/10 text-danger"}`}
              data-testid="verify-result"
            >
              {verification.verified ? (
                <>
                  <ShieldCheck className="h-4 w-4" aria-hidden="true" /> Chain intact — {verification.checked_rows} of {verification.total_rows} records verified.
                </>
              ) : (
                <>
                  <ShieldAlert className="h-4 w-4" aria-hidden="true" /> Chain broken at row {verification.broken_row_id}. Records after this point are untrusted.
                </>
              )}
            </div>
          ) : null}

      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex gap-2">
              {decisions.map((d) => (
                <Button key={d} size="sm" variant={decisionFilter === d ? "default" : "outline"} onClick={() => setDecisionFilter(d)}>
                  {d === "ALL" ? "All" : d.replace(/_/g, " ")}
                </Button>
              ))}
            </div>
            <Input placeholder="Search company, metric, or thread" value={query} onChange={(e) => setQuery(e.target.value)} className="max-w-xs" aria-label="Search audit log" />
            {threadFilter ? (
              <button
                type="button"
                onClick={() => setSearchParams({})}
                className="rounded-full border px-3 py-1 text-xs font-medium hover:bg-accent"
                data-testid="thread-filter"
              >
                run {threadFilter} ✕
              </button>
            ) : null}
          </div>

          {isLoading ? (
            <div className="h-40 animate-pulse rounded-lg bg-muted" />
          ) : error || !rows ? (
            <div className="rounded-xl border p-4 text-sm">Failed to load audit log.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Timestamp</th>
                    <th className="py-2 pr-4 font-medium">Company</th>
                    <th className="py-2 pr-4 font-medium">Metric</th>
                    <th className="py-2 pr-4 font-medium">Decision</th>
                    <th className="py-2 pr-4 font-medium">Original</th>
                    <th className="py-2 pr-4 font-medium">Corrected</th>
                    <th className="py-2 pr-4 font-medium">Reviewer note</th>
                    <th className="py-2 pr-4 font-medium">Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((r) => (
                    <tr
                      key={r.id}
                      onClick={() => setSelectedRow(r)}
                      className="cursor-pointer border-b last:border-0 hover:bg-accent/40"
                    >
                      <td className="py-2.5 pr-4 text-muted-foreground">{formatDateTime(r.timestamp)}</td>
                      <td className="py-2.5 pr-4 font-medium">{r.company_name}</td>
                      <td className="py-2.5 pr-4">{r.metric_name}</td>
                      <td className="py-2.5 pr-4">
                        <DecisionBadge decision={r.decision} />
                      </td>
                      <td className="py-2.5 pr-4 tabular-nums">{formatUsdFull(r.original_value)}</td>
                      <td className="py-2.5 pr-4 tabular-nums">{r.corrected_value === null ? "—" : formatUsdFull(r.corrected_value)}</td>
                      <td className="py-2.5 pr-4 text-muted-foreground">{r.reviewer_notes || "—"}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs">{r.row_hash.slice(0, 10)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visibleRows.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">No audit records match your filters.</p> : null}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(selectedRow)} onOpenChange={(open) => !open && setSelectedRow(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Audit record</DialogTitle>
          </DialogHeader>
          {selectedRow ? (
            <div className="space-y-2 text-sm">
              <div>
                <span className="text-muted-foreground">Row ID:</span> <code>{selectedRow.id}</code>
              </div>
              <div>
                <span className="text-muted-foreground">Prev hash:</span> <code>{selectedRow.prev_hash}</code>
              </div>
              <div>
                <span className="text-muted-foreground">Row hash:</span> <code>{selectedRow.row_hash}</code>
              </div>
              <div>
                <span className="text-muted-foreground">Decision:</span> <DecisionBadge decision={selectedRow.decision} />
              </div>
              <div>
                <span className="text-muted-foreground">Original:</span> {formatUsdFull(selectedRow.original_value)}
              </div>
              <div>
                <span className="text-muted-foreground">Corrected:</span> {selectedRow.corrected_value === null ? "—" : formatUsdFull(selectedRow.corrected_value)}
              </div>
              <div>
                <span className="text-muted-foreground">Note:</span> {selectedRow.reviewer_notes || "—"}
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                {selectedRow.thread_id ? (
                  <Link
                    to={`/filings/${selectedRow.thread_id}`}
                    className="inline-flex items-center gap-1 text-sm text-info hover:underline"
                    onClick={() => setSelectedRow(null)}
                  >
                    Open the run
                  </Link>
                ) : null}
                {selectedRow.thread_id ? (
                  <Link
                    to={`/review?thread=${selectedRow.thread_id}`}
                    className="inline-flex items-center gap-1 text-sm text-info hover:underline"
                    onClick={() => setSelectedRow(null)}
                  >
                    Open in the review queue
                  </Link>
                ) : null}
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

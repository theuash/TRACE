import type { ThreadSummary } from "@/api/types";

export function latestRunPerTicker(threads: ThreadSummary[] | undefined): ThreadSummary[] {
  const newest = new Map<string, ThreadSummary>();
  for (const thread of threads ?? []) {
    const current = newest.get(thread.ticker);
    if (!current || thread.updated_at > current.updated_at) newest.set(thread.ticker, thread);
  }
  return [...newest.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

export function isPendingReview(thread: ThreadSummary): boolean {
  return thread.status === "PAUSED_FOR_REVIEW" || thread.status === "HUMAN_REVIEWED";
}

export function pendingItemCount(threads: ThreadSummary[] | undefined): number {
  return latestRunPerTicker(threads)
    .filter(isPendingReview)
    .reduce((total, thread) => total + (thread.flagged_count ?? 0), 0);
}

export function dataModeLabel(): string {
  return "Live data";
}

export function dataModeTone(): string {
  return "bg-success/15 text-success";
}

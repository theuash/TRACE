/**
 * Demo prefetch — pre-warms the in-browser mock API so the first user
 * interaction on any page is instant and the demo never shows a loading state
 * when it doesn't have to.
 *
 * Run in the browser console (dev only) or import from the demo entry:
 *
 *   await prefetchDemo();
 */

import { createTraceApi } from "@/api/client";
import type { StartAuditRequest } from "@/api/types";

export async function prefetchDemo(): Promise<void> {
  const api = createTraceApi();

  // Warm the company catalogue.
  await api.listCompanies();

  // Warm a paused demo audit for each of the five companies.
  const requests: StartAuditRequest[] = [
    { cik: "0000320193", confidence_threshold: 0.85, yoy_threshold_pct: 0.3, demo_only: true },
    { cik: "0000789019", confidence_threshold: 0.85, yoy_threshold_pct: 0.3, demo_only: true },
    { cik: "0001045810", confidence_threshold: 0.85, yoy_threshold_pct: 0.3, demo_only: true },
    { cik: "0001318609", confidence_threshold: 0.85, yoy_threshold_pct: 0.3, demo_only: true },
    { cik: "0001018724", confidence_threshold: 0.85, yoy_threshold_pct: 0.3, demo_only: true },
  ];

  const settled = await Promise.allSettled(requests.map((r) => api.startAudit(r)));
  const ok = settled.filter((r) => r.status === "fulfilled").length;
  // Prefetching creates threads in localStorage; the user can reset via Settings.
  void ok;
}

/** Fire-and-forget helper used by the Guided Demo drawer. */
export function prefetchDemoBackground(): void {
  void prefetchDemo().catch(() => {
    // Prefetch is best-effort; failures are non-fatal.
  });
}

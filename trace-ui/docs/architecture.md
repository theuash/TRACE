# TRACE UI — Architecture

## Overview

The TRACE web UI is a standalone React 18 + TypeScript + Vite application with a
TanStack Query data layer and a pluggable API backend. The UI never talks to the backend
directly through feature code; it goes through the `TraceApi` interface.

## Layers

```
src/
  api/
    types.ts        # shared contract types (single source for the UI)
    contract.ts     # TraceApi interface
    client.ts       # createTraceApi() — factory switching on VITE_API_MODE
    http.ts         # fetch-backed implementation (VITE_API_BASE)
    mock/
      server.ts     # MockTraceApi — in-browser stateful demo server
      fixtures.ts   # companies, metrics, flagged items, XBRL truth
      hash.ts       # SHA-256 audit hash chain + verifier
  hooks/
    use-trace.ts   # TanStack Query hooks (incl. polling for running threads)
  components/
    ui/            # shadcn-style primitives
    layout/        # app shell, sidebar, topbar, demo pill
    *.tsx          # shared components (badges, confidence bar, KPI, stepper)
  pages/
    overview, new-audit, review-queue, filings, filing-detail,
    accuracy, audit-log, settings
  lib/
    utils.ts, format.ts
  App.tsx          # routes
  main.tsx, index.css
```

## Data flow

1. A page calls a hook (`useThreads`, `useThreadStatus`, `useStartAudit`, ...).
2. The hook wraps the query/mutation in TanStack Query.
3. The query key identifies the resource; mutations invalidate related keys.
4. The API implementation (mock or http) is chosen once at module load via
   `createTraceApi()` based on `VITE_API_MODE`.

## Running threads

- `useThreadStatus(threadId)` polls every 2s while the status is not terminal
  (`COMPLETED` / `FAILED`).
- `resume` runs the decision + hash-chain append, then completion.

## Hash chain

Mock implementation uses Web Crypto SHA-256 over a `|`-joined payload of
`(prev_hash, id, thread_id, company_name, metric_name, decision, original_value,
corrected_value, reviewer_notes, timestamp)`. The verifier recomputes and reports
the first broken row.

## Modes

| Mode | Environment | Behaviour |
|---|---|---|
| Mock | `VITE_API_MODE=mock` (default) | In-browser stateful mock with localStorage persistence, seeded fixtures, hash chain, tamper, failure sim. |
| HTTP | `VITE_API_MODE=http` | `HttpTraceApi` against `VITE_API_BASE` (default `http://127.0.0.1:8000`). |

Only the implementation behind the interface changes; the UI does not.

## Testing

- Unit/component: none yet beyond e2e.
- E2E: `e2e/smoke.spec.ts` — run audit → paused → queue → approve → submit → verify chain.

## Demo controls

- Settings → Reset demo data (clears localStorage threads/logs).
- Settings → Simulate failure (forces `FAILED` status).
- Settings → Tamper with last audit row (mock only; breaks chain → red verify state).

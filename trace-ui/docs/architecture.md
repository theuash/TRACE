# TRACE UI — Architecture

## Overview

The TRACE web UI is a standalone React 18 + TypeScript + Vite application with a
TanStack Query data layer. The UI never talks to the backend directly through feature
code; it goes through the `TraceApi` interface.

## Layers

```
src/
  api/
    types.ts        # shared contract types (single source for the UI)
    contract.ts     # TraceApi interface
    client.ts       # createTraceApi() — returns the HTTP implementation
    http.ts         # fetch-backed implementation (VITE_API_BASE)
  hooks/
    use-trace.ts   # TanStack Query hooks (incl. polling for running threads)
  components/
    ui/            # shadcn-style primitives
    layout/        # app shell, sidebar, topbar
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
4. `createTraceApi()` returns `HttpTraceApi`, which talks to the real backend at
   `VITE_API_BASE` (default `http://127.0.0.1:8000`).

## Running threads

- `useThreadStatus(threadId)` polls every 2s while the status is not terminal
  (`COMPLETED` / `FAILED`).
- `resume` records the decision in the backend, which appends to the audit chain.

## Hash chain

The backend owns the hash chain: every decision is appended server-side to
`audit_entries`, which is append-only at the database level and hash-linked row to row.
`GET /audit-logs/verify` recomputes the chain and reports the first broken row.

## Testing

- Unit/component: none yet beyond e2e.
- E2E: `e2e/smoke.spec.ts` — run audit → paused → queue → approve → submit → verify chain.

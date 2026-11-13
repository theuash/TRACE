# TRACE — Financial Filing Auditor

> **Automate the routine. Escalate the uncertain. Keep every decision accountable.**

TRACE is a human-in-the-loop auditor for SEC 10-K filings. It extracts eight core financial
metrics from public filings, scores confidence from deterministic signals, validates them against
policy, escalates the uncertain to a human reviewer, and keeps every decision accountable in an
append-only audit log.

This repository contains the **production web UI** for TRACE.

---

## Tagline

> Automate the routine. Escalate the uncertain. Keep every decision accountable.

---

## Quick start

```bash
# 1. Install
npm install

# 2. Configure API mode (optional)
cp .env.example .env

# 3. Run the dev server
npm run dev          # http://localhost:5173

# 4. Run the production build
npm run build

# 5. Run the e2e smoke test
npx playwright test
```

### Scripts

| Script | Command | Purpose |
|---|---|---|
| Dev | `npm run dev` | Vite dev server on port 5173 |
| Build | `npm run build` | `tsc --noEmit` + Vite production build |
| Preview | `npm run preview` | Serve the production build |
| E2E | `npm run test:e2e` | Playwright smoke test |
| Lint | `npm run lint` | ESLint |
| Format | `npm run format` | Prettier |

---

## The nine workflow steps

1. Filing retrieval
2. Extraction
3. Confidence scoring
4. Validation
5. Automated decision
6. Human review
7. Decision and resume
8. XBRL verification
9. Audit history

---

## Pages

| Route | Page | Purpose |
|---|---|---|
| `/` | Overview | KPIs, needs-attention queue, auto-vs-escalated chart, recent filings |
| `/new` | New audit | Company selection, thresholds, live workflow stepper, run status |
| `/review` | Review queue | Ramp-style split view, evidence, confidence breakdown, decisions |
| `/filings` | Filings | Filing list with status, flagged/auto counts, accuracy |
| `/filings/:id` | Filing detail | Metrics / Validation / Workflow / Accuracy tabs |
| `/accuracy` | Accuracy | Final vs original accuracy, auto-approval accuracy, precision, recall, per-metric table, CSV export |
| `/audit` | Audit log | Append-only rows, hash-chain verification, row drawer |
| `/settings` | Settings | Data source, policy defaults, data store, appearance |

---

## Data layer

### API contract

The single source of truth is the `TraceApi` interface in
[`src/api/contract.ts`](src/api/contract.ts), with types in
[`src/api/types.ts`](src/api/types.ts).

Methods:

- `health()`
- `listCompanies()`
- `startAudit({ cik, confidence_threshold, yoy_threshold_pct })`
- `listThreads()`
- `getStatus(threadId)`
- `getTimeline(threadId)`
- `resume(threadId, { decisions })`
- `listAuditLogs(filters)`
- `verifyChain()`
- `getReport()`, `getThresholds()`, `setThresholds()`, `estimateEscalations()`
- `getDatabase()`, `pingDatabase()`

### Implementation

| Implementation | Path |
|---|---|
| HTTP | [`src/api/http.ts`](src/api/http.ts) |

The dashboard always talks to the real backend:

```bash
VITE_API_BASE=http://127.0.0.1:8000
```

The UI imports only the `TraceApi` interface; never an implementation.

### Data honesty

The sidebar shows a **Live data** badge. Every number on screen comes from the real workflow:
filings are read from the cached SEC HTML, verification against XBRL Company Facts happens in
the backend, and the audit chain is owned by the database.

---

## Pages in detail

### Overview

- KPI cards: pending reviews, completed audits, auto-approved, escalated, accuracy, escalation precision.
- "Needs your attention" list.
- Auto-approved vs. escalated bar chart.
- Recent filings table.

### New audit

- Company cards (multi-select).
- Confidence threshold slider (default 0.85), YoY tolerance slider (default 30%).
- Run audit / Run all companies.
- Live nine-step workflow stepper with state per step, timestamps, and a
  **"Paused at checkpoint"** chip linking to the review queue.

### Review queue

- Split view: list on the left, detail pane on the right (Ramp-style).
- Filter tabs: Pending / Decided / All.
- Progress bar: n of m reviewed.
- Confidence score with `confidence_signals` breakdown (hover).
- Plain-English escalation reasons.
- Source snippet with `matched_text` highlighted (monospace, money regex).
- Approve / Correct / Reject + reviewer note.
- No default selection; Approve disabled until a correction or note is entered.
- Bulk approve with confirmation dialog.
- Keyboard shortcuts: `J`/`K` navigate, `A` approve, `C` correct, `R` reject, `⌘/Ctrl+Enter` submit.

### Filings / Filing detail

- List with status, flagged/auto counts, accuracy.
- Detail header: company, CIK, FY, period end, copyable thread id, filing link.
- Tabs: Metrics / Validation / Workflow / Accuracy.

### Accuracy

- Final accuracy, original accuracy, auto-approval accuracy, auto-approved vs. escalated counts.
- Escalation precision overall and by type, escalation recall.
- Per-metric accuracy table, bar chart, CSV export.
- "How these numbers are computed" expander.

### Audit log

- Append-only table with lock icon + "Append-only" label.
- Verify chain button (green intact / red broken).
- Row drawer with prev hash and row hash.

### Settings

- Data source status + connection test.
- Policy defaults.
- Data store panel (backend, host, row counts, ping).
- Theme.

---

## Visual system

- Light default + fully polished dark theme (CSS variables).
- Deep indigo accent (`#4F46E5` family), slate neutrals.
- Semantic colors: green (passed/approved), amber (flagged/pending), red (failed/rejected), blue (running), grey (skipped).
- Tabular numerals on all figures; full USD with thousands separators plus compact form.
- 8px grid, 12px radius cards, 1px borders, minimal shadows.
- 1024–1920px usable.
- Skeletons, empty states, error states with retry; WCAG AA; visible focus rings; reduced motion respected.

---

## Engineering notes

- All server data via TanStack Query hooks; poll running audits every 2s until terminal state.
- Components in small files; no dead code; no console errors.
- Never hardcode statistics in components: every number rendered comes from the `TraceApi`.

---

## Acceptance

- `npm run build` passes with zero TypeScript errors.
- `npx playwright test` passes against the real backend (full reviewer journey).
- Lighthouse accessibility ≥ 90 on the review queue (target; not yet measured in this environment).

---

## Not included / roadmap

- Threshold sliders with live `estimate_escalations` before/after (`POST /thresholds/estimate` is live; the UI slider is not wired yet).
- Adaptive threshold *suggestions* from reviewer behaviour (must stay human-applied and audited).

### What the backend now serves

`api/main:app` implements every route in this contract against `workflow.service`.
The translation from workflow contracts to these JSON shapes lives in `api/adapters.py`.

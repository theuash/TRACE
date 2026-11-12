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
| `/settings` | Settings | Data source, policy defaults, demo controls, appearance, danger zone |

---

## Data layer

### API contract

The single source of truth is the `TraceApi` interface in
[`src/api/contract.ts`](src/api/contract.ts), with types in
[`src/api/types.ts`](src/api/types.ts).

Methods:

- `health()`
- `listCompanies()`
- `startAudit({ cik, confidence_threshold, yoy_threshold_pct, demo_only })`
- `listThreads()`
- `getStatus(threadId)`
- `getTimeline(threadId)`
- `resume(threadId, { decisions })`
- `listAuditLogs(filters)`
- `verifyChain()`

Plus demo/dev controls required by the acceptance flow:

- `resetDemo()`
- `tamperWithLastRow()`
- `setFailureMode(enabled)`

### Implementations

| Implementation | Path | Default |
|---|---|---|
| Mock | [`src/api/mock/`](src/api/mock/) | **Yes** |
| HTTP | [`src/api/http.ts`](src/api/http.ts) | No |

Switch with the `VITE_API_MODE` environment variable:

```bash
VITE_API_MODE=mock    # default — fully in-browser demo server
VITE_API_MODE=http    # real backend at VITE_API_BASE (default http://127.0.0.1:8000)
```

The UI imports only the `TraceApi` interface; never an implementation.

### Mock behaviours

- Five companies seeded: Apple (`AAPL`), Microsoft (`MSFT`), NVIDIA (`NVDA`), Tesla (`TSLA`),
  Amazon (`AMZN`).
- Eight metrics per company (revenue, net income, total assets, total liabilities, shareholders'
  equity, operating cash flow, cash and cash equivalents, research and development).
- Start-audit pipeline advances through the workflow steps with realistic latency, then either
  completes or pauses at the human-review checkpoint.
- Flagged mix: Apple `Revenue` (`EXTRACTION_RISK`, HIGH), Tesla `Revenue` (`FINANCIAL_ANOMALY`, HIGH),
  Amazon `Operating Cash Flow` (`EXTRACTION_RISK`, MEDIUM). NVDA and MSFT have no flags.
- Resume applies decisions, appends SHA-256 hash-chain audit rows, then completes with an accuracy
  report computed from fixtures.
- State persists in `localStorage` (checkpoint/resume).
- `verifyChain()` recomputes hashes; `tamperWithLastRow()` breaks the chain for the tamper demo.
- Failure simulation toggle for error states.

### Honest demo indicator

While in mock mode the top bar and sidebar show a subtle **"Demo data"** pill. In HTTP mode it shows
**Live**. Mock numbers are never presented as live SEC results.

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
- "Demo: force pause" switch (clearly labelled demo preset).
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
- Demo-only runs excluded by default with a visible toggle.
- "How these numbers are computed" expander.

### Audit log

- Append-only table with lock icon + "Append-only" label.
- Verify chain button (green intact / red broken).
- Row drawer with prev hash and row hash.

### Settings

- Data source mode + connection test (http mode).
- Policy defaults.
- Reset demo data, simulate failure, tamper with last row (mock only), theme.

---

## Guided demo

Open the **Guided demo** from the top bar:

1. Run a demo audit (Apple, force-pause).
2. Inspect a flagged item.
3. Make a decision.
4. View accuracy.
5. Verify the audit chain.

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
- `npx playwright test` passes (full mock e2e lifecycle).
- Lighthouse accessibility ≥ 90 on the review queue (target; not yet measured in this environment).
- Switching `VITE_API_MODE=http` only changes the data source, never the UI code.

---

## Not included / roadmap

- Real backend wiring for all verification, workflow, audit, validation modules.
- Threshold sliders with live `estimate_escalations` before/after.
- "Corrupt a value" fault injection via `FaultSpec` in `RunRequest`.

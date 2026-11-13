# TRACE architecture

One agent, three jobs: read a filing, prove the numbers, and stop for a human when the proof fails.

```
                 ┌──────────── extraction (P1) ────────────┐
  SEC 10-K ───▶  │ fetch_filing → extract_filing → score   │  ──▶ ExtractedMetric[]
                 └────────────────────────────────────────┘
                                        │
                 ┌──────────── trust layer (P2) ───────────┐
                 │ run_validations → decide (green/yellow/red)
                 │ review_gate: interrupt() when not green │  ──▶ EscalationItem[]
                 └────────────────────────────────────────┘
                                        │  (human decides, on the dashboard)
                 ┌──────────── verification (P3) ──────────┐
                 │ SEC Company Facts → truth value per metric
                 │ build_report → accuracy, precision, calibration
                 └────────────────────────────────────────┘
```

## The trust rule

XBRL is **only** used in `verification/`, after a human decision. Extraction never looks at it, so
the answer key cannot leak into the numbers being judged. Confidence is a parse-quality score built
from fixed deterministic signals, never a model's opinion and never a comparison with the truth.

## Layers and owners

| Layer | Folder | Owner | Contract |
|---|---|---|---|
| Extraction | `extraction/`, `llm/`, `mcp_server/` | P1 | `fetch_filing`, `extract_filing`, `score_extraction`, `explain_anomaly` |
| Trust layer | `workflow/`, `audit/`, `validation/` | P2 | `run_validations`, `decide`, `workflow_service` |
| Verification + surface | `verification/`, `api/`, `trace-ui/`, `docs/` | P3 | `verify_company`, `build_report`, `api.main:app` |

Nobody imports a teammate's module directly. Every cross-folder call goes through
`load_provider("<name>")` in `shared/interfaces.py`, so a module can be replaced by a fake without
touching the caller (`USE_FAKES=true`).

## The database (Neon PostgreSQL)

Everything that has to survive a restart lives in PostgreSQL. The filing and XBRL caches stay on
disk in `data/` - they are caches, not the database.

| Table | Holds | Written by |
|---|---|---|
| `runs` | one row per run: id, ticker, status, error, timestamps | the workflow |
| `kv` | the live thresholds (one JSON value) | the workflow |
| `side_effects` | `(run_id, step, item_id) -> payload`, the idempotency ledger | the workflow |
| `audit_entries` | the sealed decision log: `seq`, canonical `payload`, `hash` | `audit/log.py` only |
| `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` | the LangGraph state snapshots | the checkpointer |

Two rules the schema enforces, not the application:

1. **The audit log is append-only.** A `BEFORE UPDATE OR DELETE` trigger raises, and so does
   `BEFORE TRUNCATE`. Only the migration/reset path may lift the trigger, and even then the
   chain verifier catches any change that slips through.
2. **The chain itself.** Every row stores the hash of the row before it, so a change that bypassed
   the database would still be detected by `audit/verify.py`.

### Neon specifics

- The **direct** URL is preferred for the app: the pooler adds a PgBouncer hop to every query
  (~1.2 s each in this environment, ~50 ms direct). The pooled URL is the fallback and the right
  choice for a serverless deployment.
- The pooler refuses session parameters in the startup packet (`statement_timeout`,
  `search_path`). So the timeout is set per transaction with `SET LOCAL`, and schema isolation
  (used by the tests) needs the direct URL.
- A free Neon branch suspends when it is idle: the first query after a pause takes a few seconds.
  The API pings with one retry, `/health` reports the last round trip instead of making a new one,
  and the dashboard shows "connecting" instead of hanging.

### The API (Person 3)

`api/main.py` is a thin wrapper over the `WorkflowService` protocol. It never computes a tier, a
statistic or a hash itself: `api/adapters.py` translates the contract objects into the JSON shape
that `trace-ui/src/api/types.ts` defines.

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness **and** which data source is behind it (`mode: mock | real`) |
| `GET /threads` | one row per run (newest first) |
| `GET /threads/{id}/status` | metrics, validations, flagged items, thresholds, accuracy for that run |
| `POST /audits` | start a run for a CIK |
| `POST /threads/{id}/resume` | record human decisions |
| `GET /audit-logs`, `GET /audit-logs/verify` | the append-only log and its hash-chain check |
| `GET|POST /thresholds`, `POST /thresholds/estimate` | policy, applied changes, and the dry-run counter |
| `GET /report` | accuracy for every audited company, measured against XBRL |
| `GET /database`, `POST /database/ping` | which store is behind the app: host, latency, row counts, last write |

### Three scoping rules the API enforces

1. **One row per metric.** Metric ids are `(ticker, metric, fiscal_year)`, so re-auditing a company
   produces the same ids again. Metrics and reviews are de-duplicated by id, and the status payload
   shows only the current fiscal year (the year before it is the comparison column).
2. **One queue per run.** Reviews carry no run id, so the API keeps the newest ones and only as many
   as the run is actually waiting for (`RunSummary.pending_reviews`).
3. **One report per audience.** `/threads/{id}/status` carries the report of *that* company;
   `/report` aggregates every audited company.

## The reviewer experience (Person 3)

`trace-ui` is React + Vite + TypeScript. It talks to the API and nothing else - no workflow import,
no rule evaluation, no tier decision. Anything the reviewer sees is computed by the server and
rendered here.

- `src/api/contract.ts` - the API surface the UI may call.
- `src/api/http.ts` / `src/api/mock/server.ts` - the two implementations of that surface.
- `src/hooks/use-trace.ts` - react-query hooks; polling stops when a run reaches a terminal state.
- `src/pages/*` - one page per question the reviewer asks.
- `src/lib/threads.ts` - the "newest run per company" rule, shared by every page.

The review queue is the product. A flagged value has to be understandable in 30 seconds:

1. the value, its unit and period, and the tier the server computed;
2. the confidence score *and* its signals, with the reminder that confidence measures how cleanly
   the number was read - not whether it is right;
3. the plain-English reason (the failed accounting rule, in full sentences, not "check failed");
4. the exact text from the filing, with the matched substring highlighted;
5. Approve / Correct / Reject, with Approve locked until the reviewer writes a note;
6. the decision lands in the hash-chained audit log, which the reviewer can verify on the next page.

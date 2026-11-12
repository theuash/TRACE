# PLAN_P2: Workflow Engine and Trust Layer

Owner: Person 2 (`workflow/`, `audit/`, `validation/`, `tests/workflow/`, `tests/audit/`, `tests/validation/`).
Contract additions in `shared/` are made by HEAD in step 0 only.

Order is deliberate: nothing depends on Person 1 or Person 3 finishing, because `workflow/fakes.py` satisfies every
cross-team call. Every test runs with `USE_FAKES=true`.

## Step 0 - contract delta (HEAD, additive, breaks nobody)

| Change | Why |
|---|---|
| `RiskTier` StrEnum (`green`, `yellow`, `red`) | one vocabulary for P2 to emit and P3 to render |
| `Thresholds.confidence_critical: float = 0.60` | the Red boundary must move with the slider, not be hardcoded |
| `EscalationItem.tier: RiskTier = RiskTier.YELLOW` | P3 renders the colour P2 computed; nobody re-derives it |
| `Thresholds` validator | `confidence_critical <= confidence`, else everything is Red |

Acceptance: `tests/shared/test_contracts.py` passes; no field renamed or removed.

## Step 1 - `workflow/fakes.py`

Stand-ins matching `shared/interfaces.FAKES` exactly: `fetch_filing`, `extract_filing`, `score_extraction`,
`explain_anomaly`, `verify_company`, `build_report`.

- Apple-shaped 8 metrics, current + prior year, plausible `Decimal` values, real `SourceEvidence`.
- One deliberately broken value so the accounting check can fail without fault injection.
- `explain_anomaly` returns a fixed sentence and never touches a model.

Acceptance: `load_provider("fetch_filing", use_fakes=True)` returns a `FilingRef`; the fake `ExtractionResult`
validates against Pydantic.

## Step 2 - `audit/log.py` + `audit/verify.py`

- SQLite, `INSERT` only, `BEFORE UPDATE` / `BEFORE DELETE` triggers `RAISE(ABORT)`.
- `append(entry) -> AuditEntry` seals via `AuditEntry.seal()` and links `prev_hash` to the last row.
- `verify_chain()` recomputes every hash and returns `AuditVerification`.

Acceptance: tampering with one row makes verification fail with `first_broken_seq` set; `UPDATE`/`DELETE` raise.

## Step 3 - `validation/checks.py` + `validation/engine.py`

Three checks, each returning a `ValidationResult` with a plain-English `detail`:

- `accounting_equation`: assets vs liabilities + equity, tolerance `accounting_tolerance_pct`, `severity=ERROR`.
- `segment_sum`: segments vs reported total, tolerance `segment_tolerance_pct`, `severity=ERROR`.
- `yoy_change`: |change| vs `yoy_change_pct`, `severity=WARNING`; a missing prior value is `severity=ERROR`
  with `EscalationKind.MISSING_VALUE` in the reason (never silently skipped).

`engine.run_validations(result, thresholds)` runs all three and returns **passed and failed** rows.

Acceptance: a correct fixture passes all three; each single injected error trips exactly one check with the right
`metric_ids`.

## Step 4 - `validation/decide.py`

Tier from both axes, never from confidence alone:

| | all checks pass | `warning` failure | `error` failure / missing |
|---|---|---|---|
| `conf >= thresholds.confidence` | GREEN | YELLOW | RED |
| `critical <= conf < confidence` | YELLOW | YELLOW | RED |
| `conf < confidence_critical` | YELLOW | RED | RED |

- A failed check escalates every id in `ValidationResult.metric_ids` - that is the math override.
- `explain_anomaly` is called once per failed check, via `load_provider`, sentence cached by `(metric_id, check)` so
  a resume never calls the model twice; any exception falls back to the deterministic template.

Acceptance: the matrix is covered by a parametrised test; a 0.99-confidence metric failing the accounting equation is
RED; the explainer is called exactly once per failed check across two runs with the same cache.

## Step 5 - `workflow/idempotency.py`

`SQLite` table `side_effects (run_id, step, item_id, created_at, PRIMARY KEY(run_id, step, item_id))`.

- `run_once(run_id, step, item_id, fn)` returns the cached result if the key exists, otherwise executes and records.
- `counts(run_id) -> dict[str, int]` feeds `RunSummary.side_effect_counts` (every value must stay 1).

Acceptance: calling `run_once` twice with the same key executes the callable once; `counts` reports 1.

## Step 6 - `workflow/graph.py` + `workflow/service.py` + `workflow/fault.py`

Nodes in order:
`fetch_filing, extract, score, validate, decide, review_gate, apply_decisions, verify, report`.

- `review_gate` is its own node: `interrupt()` first, no side effects before it, resumed with `Command(resume=...)`.
- Checkpointer `SqliteSaver` on `data/checkpoints.db`; `thread_id == run_id`, one per company.
- Every fetch / extraction / audit write goes through `run_once`.
- `fault.py` applies a `FaultSpec` immediately after extraction, before validation.
- `service.py` implements the full `WorkflowService` Protocol; `submit_decision` refuses an APPROVE on a RED item
  unless `note` is set; `set_thresholds` writes a `threshold_change` audit row.

Acceptance: `tests/workflow/test_kill_resume.py` starts a run, pauses, closes the graph, reopens it, submits a
decision and completes - with every `side_effect_counts` value exactly 1.

## Step 7 - stretch: `validation/adaptive.py`

Reviewer behaviour produces a **suggestion** for `per_metric_confidence`. Nothing mutates automatically; applying it
goes through `set_thresholds` and writes a `threshold_change` audit entry.

## Definition of done

A paused run survives a process restart; resuming repeats no fetch, extraction or audit entry; the chain verifies and
fails when tampered; every decision, auto-approval and escalation is audited; no Green value has a failed check.

---

## Status (implemented on the current branch, HEAD-authored)

| Step | State |
|---|---|
| 0 contract delta | done: `RiskTier`, `Thresholds.confidence_critical`, `EscalationItem.tier`, validator |
| 1 `workflow/fakes.py` | done, 8 metrics + prior year + segments, `corrupt=True` for tests, call counters |
| 2 `audit/log.py` + `audit/verify.py` | done, triggers `RAISE(ABORT)`, tamper and invalid-row detection |
| 3 `validation/checks.py` + `engine.py` | done, 10 results on a clean filing, exact `detail` |
| 4 `validation/decide.py` | done, both-axis matrix, math override, explainer cached per failed check |
| 5 `workflow/idempotency.py` | done, `(run_id, step, item_id)` with payload replay |
| 6 `graph.py` + `service.py` + `fault.py` | done, pause/resume, red guard, threshold audit, dry-run estimate |
| 7 `validation/adaptive.py` | not started (stretch) |

Tests: 27 passing, including the two-process kill-and-resume (`tests/workflow/test_kill_resume.py`).

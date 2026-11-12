---
description: PERSON 2 - Workflow engine, pause/resume, audit log, validation, decisions
mode: primary
temperature: 0.1
# Optional hard lock (needs a recent OpenCode). Uncomment to make edits outside your folders denied:
# permission:
#   edit:
#     "*": deny
#     "workflow/**": allow
#     "audit/**": allow
#     "validation/**": allow
#     "tests/workflow/**": allow
#     "tests/audit/**": allow
#     "tests/validation/**": allow
#     "docs/requests/**": allow
---
You are working with **Person 2: Workflow Engine and Trust Layer**. Read `AGENTS.md` and `VISION.md` first.

## You own (edit only these)
`workflow/`, `audit/`, `validation/`, `tests/workflow/`, `tests/audit/`, `tests/validation/`

## You never edit
`extraction/`, `llm/`, `mcp_server/` (Person 1) · `verification/`, `api/`, `ui/`, `demo/`, `docs/` (Person 3) ·
`shared/` (frozen). Before each edit confirm the path is yours. Otherwise write `docs/requests/p2-to-pX-<topic>.md`.

## What you deliver (exact names, see `shared/interfaces.py`)
- `validation.engine.run_validations(result, thresholds) -> list[ValidationResult]`
- `validation.decide.decide(result, validations, thresholds) -> AutoDecision`
- `workflow.service.get_service() -> WorkflowService` (the full Protocol in `shared/interfaces.py`)
- `workflow/fakes.py`: stand-ins for P1 and P3 functions so you are never blocked (`USE_FAKES=true`)
- `audit/`: the append-only hash-chained log and its verifier

## Your mission
Make the system **reliable and accountable**. Workflow Reliability and Auditability are yours, and a single repeated side
effect after resume loses points.

## Order of work
1. `workflow/fakes.py` first, returning fixture-shaped data, so the graph runs on day one.
2. `workflow/graph.py`: LangGraph nodes in order `fetch_filing, extract, score, validate, decide, review_gate,
   apply_decisions, verify, report`. Call teammates only via `load_provider(...)`. One `thread_id` (= `run_id`) per company.
3. `review_gate` in its own node using `interrupt()`, resumed by `Command(resume=...)`, with `SqliteSaver`
   or `AsyncSqliteSaver`. No side effects before the interrupt.
4. `workflow/idempotency.py`: table keyed `(run_id, step, item_id)`; every fetch, extraction and audit write goes through it.
   Maintain `RunSummary.side_effect_counts` (every value must stay 1).
5. **Kill-and-resume test:** start, pause, kill the process, restart, submit a decision, finish with zero repeats.
6. `audit/log.py`: SQLite, triggers that RAISE on UPDATE/DELETE, hash chain via `AuditEntry.seal()`. `audit/verify.py`
   returns `AuditVerification`. Test that a tampered row is detected.
7. `validation/checks.py`: accounting equation, segment sum, year-on-year, each with plain-English `detail`.
   Return passed and failed results. `validation/engine.py` runs them.
8. `validation/decide.py`: confidence below threshold or failed check means escalate, with reasons the reviewer understands.
9. `workflow/service.py`: implement the Protocol; `estimate_escalations()` dry-run for the threshold sliders;
   `workflow/fault.py` applies a `FaultSpec` right after extraction.
10. Parallel runs with `asyncio.gather`. Stretch: `validation/adaptive.py` (reviewer feedback tunes
    `per_metric_confidence`, still catching injected faults); call `explain_anomaly` for failed checks.

## Definition of done
A paused run survives a process restart; resuming never repeats a fetch, extraction or audit entry; the chain verifies
and fails when tampered with; every decision, auto-approval and escalation is audited.

Branches: `feat/p2-<topic>`. Run `uv run python scripts/check_ownership.py` before every PR.

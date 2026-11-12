---
description: PERSON 3 - XBRL verification, API, reviewer dashboard, demo
mode: primary
temperature: 0.2
# Optional hard lock (needs a recent OpenCode). Uncomment to make edits outside your folders denied:
# permission:
#   edit:
#     "*": deny
#     "verification/**": allow
#     "api/**": allow
#     "trace-ui/**": allow
#     "demo/**": allow
#     "docs/**": allow
#     "README.md": allow
#     "tests/verification/**": allow
#     "tests/api/**": allow
#     "tests/ui/**": allow
---
You are working with **Person 3: Verification, API and Reviewer Experience**. Read `AGENTS.md` and `VISION.md` first.

## You own (edit only these)
`verification/`, `api/`, `trace-ui/`, `demo/`, `docs/`, `README.md`, `tests/verification/`, `tests/api/`, `trace-ui/e2e/`

## You never edit
`extraction/`, `llm/`, `mcp_server/` (Person 1) · `workflow/`, `audit/`, `validation/` (Person 2) · `shared/` (frozen).
Before each edit confirm the path is yours. Otherwise write `docs/requests/p3-to-pX-<topic>.md`.

## What you deliver (exact names, see `shared/interfaces.py`)
- `verification.ground_truth.verify_company(filing, final_metrics, escalated_ids, validations) -> list[AccuracyRow]`
- `verification.report.build_report(rows) -> AccuracyReport`
- `api.main:app` (FastAPI, thin wrapper over `load_provider("workflow_service")`)
- `api.mock_service.get_service()`: the full `WorkflowService` Protocol backed by fixture data (`USE_MOCK_SERVICE=true`)
- `ui/app.py`: the Streamlit dashboard, which talks to the API only

## Your mission
Make the judges **see and feel** the system work, and make the accuracy numbers trustworthy. Verification, Human Review
Experience and the demo are yours.

## Order of work
1. `api/mock_service.py` first, with a few flagged items, so the UI has data immediately. Then `api/main.py` routes mirroring
   the Protocol (runs, metrics, validations, reviews, decision, thresholds, audit, audit/verify, report, estimate).
2. `ui/app.py` scaffold with pages Overview, Review Queue, Metrics, Audit Log, Scoreboard. `ui/api_client.py` only; never import
   workflow code.
3. Review Queue: value, tier badge (the colour **comes from the API**, never recomputed in the UI), confidence bar with
   its `confidence_signals` breakdown on hover, plain-English reasons, source snippet with `matched_text` **highlighted**,
   Approve / Edit / Reject form, pending vs completed tabs, auto-refresh. Red items pinned to the top; Approve disabled
   until the reviewer enters a correction or a note.
4. Metrics page: companies x metrics, colour-coded status, validation pass/fail panel, per-run `side_effect_counts`
   ("nothing repeated" proof).
5. Audit Log page with a **Verify log integrity** button (green or red).
6. `verification/xbrl_client.py` (own small cached SEC client, SEC User-Agent, rate limited) and `verification/tag_map.py`
   (Revenues vs RevenueFromContractWithCustomerExcludingAssessedTax, etc.; handle missing tags).
7. `verification/ground_truth.py`: per-company rows with `extraction_correct`, `final_correct`, `escalation_justified`,
   using `ACCURACY_TOLERANCE_PCT`. `verification/report.py`: totals, escalation precision, per-metric and per-company
   accuracy, **calibration buckets**.
8. Scoreboard page: auto-approved vs escalated, accuracy, escalation precision, calibration chart (Plotly).
9. Two threshold sliders — green (default 0.85) and critical (default 0.60) — using `estimate_escalations` for the
   before/after story; every applied change goes through `set_thresholds` so it lands in the audit log. A **Corrupt a
   value** button that sends a `FaultSpec` in `RunRequest`.
10. `demo/prefetch.py` to pre-warm all 5 companies, `docs/architecture.md`, `docs/demo_script.md`, backup recording plan,
    keep `README.md` accurate.

## Definition of done
A first-time viewer understands a flagged value, sees the evidence, decides, and sees the audit entry within 30 seconds,
with no explanation. The report shows real numbers against XBRL for all 5 companies.

Branches: `feat/p3-<topic>`. Run `uv run python scripts/check_ownership.py` before every PR.

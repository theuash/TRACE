# TRACE Project Progress

> Snapshot date: 2026-11-12 (from repo state on `main`, HEAD `4589fa8`)  
> Sources: `VISION.md`, `README.md`, `AGENTS.md`, `PLAN_P2.md`, `HEAD_LOG.md`, git history/status, test runs, and current file tree.

## 1) Project summary

TRACE is a human-in-the-loop financial filing auditor for SEC 10-K filings (MineArena PS-01). Target flow:
- Fetch filing (SEC EDGAR, cache-first)
- Extract 8+ metrics from filing HTML with evidence
- Score confidence deterministically (parse-quality signals, not LLM certainty/XBRL)
- Run validation checks and decide Green/Yellow/Red (with pause for review when needed)
- Support human approve/correct/reject and resume from checkpoint
- Verify against XBRL (ground truth, verification only)
- Record decisions in tamper-evident, append-only hash-chained audit log
- Show accuracy/calibration and demo reliability (kill-and-resume, fault injection)

Scope target: 5 companies (AAPL, MSFT, TSLA, NVDA, AMZN), 8 core metrics (+ optional), HTML filings, offline/demo-friendly cached flow.

## 2) Repository / environment status

- **Branch:** `main` (tracking `origin/main`). Other local branch: `contract/p2-nullable-escalation-value`.
- **Recent commits (top):** `4589fa8` merge: missing-metric escalations, learned labels, prefix-only alias tier; `0a45410` docs/log for contract+learned-label work; plus earlier extraction/workflow/contract setup commits.
- **Working tree (modified/untracked):** `.opencode/agent/person3.md`, `AGENTS.md`, `README.md`, `extraction/locate.py`, `tests/workflow/test_service.py`, `workflow/service.py`, `.env.example`, `docs/requests/p2-to-p3-api-contract.md`, `scripts/`, `tests/extraction/test_scale.py`.
- **Ownership check:** `uv run python scripts/check_ownership.py` → `nothing to check` (exit 0).
- **Lint:** `uv run ruff check .` → **5 errors** (line-length E501 in `shared/interfaces.py`, `shared/schemas.py`, and a few other locations reported).
- **Dependencies:** Python env present (`.venv`, `uv.lock`), `trace-ui/package-lock.json` present but `trace-ui/node_modules/` not installed in this workspace.

### Local data/cache state
- `data/form 10-K/`: many EDGAR submission-index JSON files present (CIKs indexed), but **no confirmed cached primary HTML filings for the 5 demo companies** visible.
- `data/filings/`: present (cache dir for downloaded filing docs/refs as implemented).
- Local DBs exist: `data/aliases.db`, `data/audit.db`, `data/checkpoints.db`, `data/idempotency.db`, `data/runs.db` (runtime artifacts; gitignored by policy).
- `tests/fixtures/`: `aapl_extraction.json`, `msft_extraction.json` committed.

### Config/secrets
- `.env` exists but key values appear unset/placeholders in file (e.g. `SEC_USER_AGENT=`, LLM settings empty in current state). `.env.example` is untracked/updated in working tree.
- `data/`, `.env*` (except example) are gitignored per rules.

## 3) What has been done

### 3.1 Contracts and shared foundation (`shared/`, frozen area)
- **Schemas/models:** `shared/schemas.py` implemented with core domain types (company/filing/metrics/evidence, extraction, validation, escalation/review, audit, accuracy, thresholds, etc.), including P2 contract delta: `RiskTier`, `Thresholds.confidence_critical`, `EscalationItem.tier`, and **nullable** `EscalationItem.value` (missing metric case).
- **Provider contracts/registry:** `shared/interfaces.py` defines Protocols and `load_provider(...)` with real/fake provider mappings for P1/P2/P3 modules.
- **Config:** `shared/config.py` includes 5 demo companies, settings/env loading, paths, thresholds defaults/helpers, SEC UA assertion helper.
- **Shared tests:** `tests/shared/test_contracts.py` present.

### 3.2 Person 1 — Extraction & LLM (`extraction/`, `llm/`)
**Implemented modules (code present):**
- `extraction/edgar.py`, `http.py`: SEC/EDGAR fetch plumbing and caching-oriented helpers.
- `extraction/locate.py`: statement/table locating, scale/period parsing support.
- `extraction/table_parser.py`: label matching/parsing, metric building helpers.
- `extraction/segments.py`: segment extraction support.
- `extraction/confidence.py`: deterministic parse-quality scoring from extraction-time signals.
- `extraction/alias_memory.py`: learned-label/alias memory (SQLite-backed, e.g. `data/aliases.db`) so model-taught labels can be reused.
- `extraction/pipeline.py`: `fetch_filing`, `extract_filing` orchestration; table parser primary, optional LLM second reader path for agreement/coverage with safeguards (LLM-only values constrained/capped per design).
- `extraction/__main__.py`: CLI to build fixtures (`--fixture`, `--all`, `--aliases`).
- `llm/client.py`: OpenAI-compatible client abstraction (provider/model/timeout config path).
- `llm/second_reader.py`: located-table row reading/label assistance for parser.
- `llm/explain.py`: anomaly explanation entry point with fallback behavior contract (per design/tests present).

**Progress/evidence:**
- `extraction/PLAN.md` reports steps 0–8 built (fetch/cache, locate, parse, confidence, segments, LLM client, explain, second reader), 47 extraction/llm-related tests passing offline, verified on AAPL and MSFT with 10 metrics and intact accounting equation; TSLA/NVDA/AMZN pending real `SEC_USER_AGENT`/runs.
- Real fixtures committed: `tests/fixtures/aapl_extraction.json`, `tests/fixtures/msft_extraction.json`.
- Extraction tests exist broadly: edgar/locate/table parser/segments/scale/label match/derived/confidence/fixture/alias memory; LLM tests exist for client/second reader/explain.

**Not done / gaps (P1):**
- `mcp_server/` not implemented (stretch).
- Remaining 3 demo-company fixtures/runs (TSLA, NVDA, AMZN) not confirmed complete in repo state.
- Offline/demo pre-warmed primary filing HTML cache for all 5 companies not confirmed.
- Some extraction tests currently error in this environment due missing fixtures/helpers (`html_file`, `make_filing`) in collected tests (see test status).

### 3.3 Person 2 — Workflow, audit, validation (`workflow/`, `audit/`, `validation/`)
**Implemented modules (code present):**
- `workflow/fakes.py`: fake providers/stand-ins for graph/service development and tests.
- `workflow/graph.py`: LangGraph workflow/orchestration (fetch→extract→score→validate→decide→review gate→apply decisions→verify→report flow per design).
- `workflow/service.py`: `WorkflowService` implementation surface (runs/reviews/metrics/validations/thresholds/audit/report/decision handling, resume-related behavior; recent edits in working tree).
- `workflow/idempotency.py`: side-effect idempotency store/helpers (`run_once`/counts pattern per plan).
- `workflow/fault.py`: fault injection support.
- `workflow/cli.py`: CLI entry for workflow interactions.
- `audit/log.py`: append-only hash-chained audit log (SQLite) with integrity protections.
- `audit/verify.py`: chain verification.
- `validation/checks.py`, `validation/engine.py`: accounting equation, segment sum, YoY checks (with plain-English details/severities).
- `validation/decide.py`: tier/decision logic using confidence + validation outcomes, escalation behavior.

**Progress/evidence:**
- `PLAN_P2.md` marks steps 0–6 done (contract delta, fakes, audit log/verify, checks/engine, decide, idempotency, graph/service/fault) and step 7 (`validation/adaptive.py`) not started.
- `HEAD_LOG.md` notes: missing core metric handling (Red escalation with `value=None`), deterministic missing-metric behavior, service/run-state improvements, alias/label-related integration changes; requests restart for agents after contract changes.
- Workflow/audit/validation tests present: `tests/workflow/test_service.py`, `test_idempotency.py`, `test_kill_resume.py` (+ script), `tests/audit/test_audit_log.py`, `tests/validation/test_checks.py`, `test_decide.py`.

**Not done / gaps (P2):**
- `validation/adaptive.py` (stretch: threshold suggestions from reviewer behavior) not implemented.
- End-to-end integration against real P1/P3 implementations (instead of fakes/mock paths) not fully confirmed from repo state.
- Some modified P2-related files are uncommitted (`workflow/service.py`, `tests/workflow/test_service.py`).

### 3.4 Person 3 — Verification, API, dashboard, demo (`verification/`, `api/`, `trace-ui/`, `demo/`, `docs/`)
**Implemented:**
- **`trace-ui/` (React + Vite + TS, substantial scaffold/UI):** full app structure with pages (`overview`, `new-audit`, `review-queue`, `filings`, `filing-detail`, `accuracy`, `audit-log`, `settings`), layout/components, hooks, formatting/utils, styling, and data layer abstractions.
  - `src/api/contract.ts` + `src/api/types.ts`: client-side API contract/types.
  - `src/api/mock/*`: in-browser mock server/fixtures/hash utilities for demo mode.
  - `src/api/http.ts` + `src/api/client.ts`: HTTP mode wiring abstraction.
  - E2E scaffold exists: `trace-ui/e2e/smoke.spec.ts`, Playwright config.
  - Docs in UI folder: `trace-ui/docs/architecture.md`, `demo_script.md`, `backup-recording-plan.md`.
  - `trace-ui/README.md` describes mock-first behavior, guided demo flow, pages, and acceptance targets.
- **`docs/requests/`:** cross-team request docs exist (P2→P1 local filing source, P2 contract nullable escalation value, P2→P3 API contract) — useful integration handoff artifacts.
- **Repo docs:** `README.md`, `VISION.md`, `AGENTS.md`, `GIT_POLICY.md`, `PLAN_P2.md`, `HEAD_LOG.md` present and informative.

**Not implemented / missing (per ownership targets):**
- `verification/` Python package/module **missing** (`verify_company`, XBRL client/tag map, report builder/calibration logic not present).
- `api/` Python backend **missing** (`api.main:app`, real/mock service wrapper per P3 contract not present at repo root package).
- `demo/` helpers **missing** (e.g. prefetch/fault/demo utilities described in plans/readme targets).
- `tests/verification/`, `tests/api/`, `trace-ui` e2e coverage beyond scaffold not confirmed executed.
- `README.md` still states `ui/app.py` (Streamlit) in layout text while actual dashboard is `trace-ui/` (React/Vite) — documentation alignment needed.
- UI currently emphasizes mock mode; real backend parity with `workflow.service` contract is pending.

## 4) Test and quality status

### Pytest (repo)
- **Most recent full run result observed:** `75 passed, 3 skipped, 5 errors in 1.90s`.
- **Passing areas include:** shared contracts, audit log, validation checks/decide, workflow service/idempotency/kill-resume (core P2), many extraction/LLM tests.
- **Errors (5, collection/setup in extraction):**
  - `tests/extraction/test_edgar.py::test_cached_filing_ref_short_circuits` — missing fixture `settings`
  - `tests/extraction/test_locate.py::test_picks_the_statement_not_the_note` — missing fixture `html_file`
  - `tests/extraction/test_locate.py::test_reads_scale_and_periods` — missing fixture `html_file`
  - `tests/extraction/test_segments.py::test_segments_sum_to_the_reported_total` — missing fixture `html_file`/`make_filing`
  - `tests/extraction/test_segments.py::test_no_segment_table_gives_an_empty_list` — missing fixture `html_file`/`make_filing`
- **Interpretation:** core logic/tests largely pass, but extraction test harness/fixtures/helpers are incomplete or mismatched for those tests in current tree.

### Ruff
- **5 lint errors** currently reported (`E501` line too long in contract/shared files among others). Needs cleanup before clean CI/PR quality bar.

### Frontend checks
- `trace-ui` dependencies not installed locally (`node_modules` absent), so `npm run build` / `npm run test:e2e` not verified in this environment.

### Ownership/policy checks
- `scripts/check_ownership.py` passes with current working set.

## 5) Known issues, risks, and integration gaps

- **P3 backend/verification gap:** No `api/` or `verification/` implementation yet; UI cannot fully run against real workflow/XBRL path without this layer.
- **Mock-vs-real integration gap:** `trace-ui` mock server exists, but HTTP contract alignment to real `WorkflowService` endpoints/shape must be completed and validated.
- **Demo data readiness:** 5-company cached filing/docs and fixture coverage incomplete (only AAPL/MSFT fixtures confirmed). TSLA/NVDA/AMZN extraction runs pending SEC UA/config and possibly downloads.
- **Environment readiness:** `.env` appears not fully configured (SEC user agent/LLM settings). Real SEC access and optional LLM behavior depend on this.
- **Test harness issues:** 5 extraction setup errors block a fully green pytest run.
- **Lint debt:** 5 ruff issues outstanding.
- **Doc drift:** README/agent docs still reference `ui/app.py` in places while implementation is `trace-ui/` (React).
- **Working tree not clean:** multiple modified/untracked files (including contract-adjacent docs/agent instructions and P2/P1 code/tests) should be reviewed/committed coherently by owners.

## 6) What is left (prioritized)

### 6.1 Must-have to reach demo-ready end-to-end (per VISION/README definition of done)
1. **Complete P3 backend integration**
   - Implement `api/` FastAPI wrapper over `load_provider("workflow_service")` (or mock-service mode) matching agreed HTTP contract.
   - Implement `api/mock_service.py` (Protocol-compatible fixture-backed service) if used for UI bring-up.
   - Wire `trace-ui` HTTP mode to real endpoints and ensure status/timeline/review/audit/report shapes match UI types.
2. **Implement verification and reporting (P3)**
   - `verification/xbrl_client.py` + `tag_map.py` (cached, rate-limited, SEC-compliant; verification only).
   - `verification/ground_truth.py` (`verify_company`) and `verification/report.py` (`build_report`, calibration buckets/accuracy metrics).
   - Integrate report generation into workflow completion path and UI scoreboard/accuracy views.
3. **Finish extraction coverage and fixtures (P1)**
   - Produce stable extraction fixtures/results for all 5 companies (including prior-year values and evidence quality checks).
   - Fix extraction test fixture/setup errors and ensure deterministic offline tests pass.
   - Confirm segment handling where available and derived metrics behavior where required.
4. **Stabilize workflow trust/demo behaviors (P2 + integration)**
   - Validate kill-and-resume, idempotency counts, and audit integrity in integrated (non-fake) flow.
   - Ensure every escalation/decision path is audited; red-approval guard enforced end-to-end.
   - Finalize fault injection pathway exposed to UI/demo controls.
5. **Demo UX completeness (P3)**
   - Review queue evidence/highlighting, confidence signal breakdown, tier rendering from API, red pinned/guarded actions.
   - Audit verify UI, metrics/validation panels, side-effect counts ("nothing repeated") visibility.
   - Threshold sliders wired to `estimate_escalations` and persisted via `set_thresholds` with audit entries.
   - Fault injection button and guided demo flow validated against real/mock service behavior.
6. **Offline/demo packaging**
   - Pre-warm/cache filings for all 5 companies (`demo/prefetch.py` or equivalent).
   - Verify demo works offline from cached data; prepare backup recording.
   - Rehearse kill-and-resume and corrupted-value escalation live.

### 6.2 Important but secondary / stretch
- `validation/adaptive.py` threshold suggestions (must remain human-applied, audited).
- `mcp_server/` wrappers (P1 stretch).
- Click-to-evidence highlighting polish, calibration chart polish, scoreboard UX refinements.
- Expand e2e coverage (`trace-ui/e2e`) for full lifecycle against chosen backend mode.
- Resolve lint issues and doc alignment (`README.md` layout/stack wording, agent instructions consistency).

## 7) Suggested next execution order (practical)

1. **Unblock green checks:** fix 5 extraction test fixture/setup errors + 5 ruff issues; rerun `uv run pytest` and `uv run ruff check .`.
2. **Lock demo data path:** set valid `SEC_USER_AGENT`, fetch/cache filings, generate fixtures for TSLA/NVDA/AMZN, confirm extraction outputs.
3. **Build P3 API bridge:** implement FastAPI + service wiring to `workflow.service` and align with `trace-ui` HTTP contract/types.
4. **Implement verification/reporting:** XBRL compare + accuracy/calibration report, then surface in UI.
5. **Integrate and rehearse demo script:** real run, forced escalation/fault, human review, kill-and-resume, audit verify, scoreboard.
6. **Freeze/demo prep:** offline cache check, backup recording, final README/docs cleanup.

## 8) Open requests / coordination notes (from repo)

- `docs/requests/p2-to-p1-local-filing-source.md`: local filing/index/cache resolution expectations for offline/demo.
- `docs/requests/p2-contract-nullable-escalation-value.md`: nullable escalation value semantics (missing ≠ 0) — UI/API must render "not found".
- `docs/requests/p2-to-p3-api-contract.md`: expected backend endpoints/status/timeline/resume/audit/demo controls for `trace-ui` HTTP mode.
- `HEAD_LOG.md` indicates contract-related agent restarts may be required for P1/P3 sessions to load updated rules/contracts.

---

**Bottom line:** Core extraction + workflow/audit/validation foundations are substantially implemented and mostly tested, with strong progress on deterministic confidence, escalation/decision logic, idempotency, and audit integrity. The main remaining work is **P3 integration and verification** (real API + XBRL/accuracy reporting + demo hardening), **full 5-company extraction/fixture readiness**, and **test/lint/demo polish** to reach the stated definition of done.
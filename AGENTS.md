# AGENTS.md: Financial Filing Auditor (MineArena PS-01)

Read `VISION.md` first (what and why). This file is how. Your role agent file adds your own task list.

## 0. Who is talking to you?

Three people, three OpenCode agents. Press **Tab** to switch, or run `opencode --agent person1|person2|person3`.
If you are the default `build`/`plan` agent and don't know who the human is, **ask which person they are
before editing anything**.

## 1. Ownership: one owner per folder, no exceptions

| Person | Role | Owns (only these may be edited) |
|---|---|---|
| **1** | Data extraction | `extraction/`, `llm/`, `mcp_server/`, `tests/extraction/`, `tests/llm/`, `tests/fixtures/` |
| **2** | Workflow engine, trust layer | `workflow/`, `audit/`, `validation/`, `tests/workflow/`, `tests/audit/`, `tests/validation/` |
| **3** | Verification, API, reviewer experience | `verification/`, `api/`, `ui/`, `demo/`, `docs/`, `README.md`, `tests/verification/`, `tests/api/`, `tests/ui/` |
| all (frozen) | Contracts | `shared/`, `tests/shared/`, `AGENTS.md`, `VISION.md`, `opencode.json`, `.opencode/`, `scripts/`, `.env.example` |

**STOP CHECK before every edit:** is this path in my row? If not, do not edit it. Instead:
1. Create `docs/requests/p<from>-to-p<to>-<topic>.md` (new, uniquely named file) describing what you need.
2. Tell the human to pass it on. Meanwhile use a fake or mock.

Exceptions: `pyproject.toml` / `uv.lock` change only via a tiny `chore/deps-<name>` branch (merge in minutes,
announce it). Contract files change only via a `contract/<topic>` branch approved by all three.
`uv run python scripts/check_ownership.py` fails if a branch touches someone else's files.

## 2. Contracts (in `shared/`, frozen)

- `shared/schemas.py`: every data shape (`ExtractedMetric`, `ValidationResult`, `EscalationItem`, `ReviewDecision`, `AuditEntry`, `AccuracyReport`, ...).
- `shared/interfaces.py`: exact function names and module paths each person must provide.
- `shared/config.py`: settings, thresholds, the 5 companies.

Never import a teammate's module directly. Call it with `load_provider("<name>")` from `shared.interfaces`.

| Provider | Module path | Owner |
|---|---|---|
| `fetch_filing` | `extraction.pipeline:fetch_filing` | P1 |
| `extract_filing` | `extraction.pipeline:extract_filing` | P1 |
| `score_extraction` | `extraction.confidence:score_extraction` | P1 |
| `explain_anomaly` | `llm.explain:explain_anomaly` | P1 |
| `run_validations` | `validation.engine:run_validations` | P2 |
| `decide` | `validation.decide:decide` | P2 |
| `workflow_service` | `workflow.service:get_service` | P2 |
| `verify_company` | `verification.ground_truth:verify_company` | P3 |
| `build_report` | `verification.report:build_report` | P3 |
| `mock_service` | `api.mock_service:get_service` | P3 |

Until teammates finish: P2 sets `USE_FAKES=true` (uses `workflow/fakes.py`); P3 sets `USE_MOCK_SERVICE=true`
(uses `api/mock_service.py`). Real implementations replace them with no code change.

## 3. Hard rules

1. **XBRL is verification only.** Extraction reads the 10-K HTML. Only `verification/` may call Company Facts.
2. **SEC etiquette.** `SEC_USER_AGENT` on every request, max 8 req/s, cache everything in `data/`, cache-first.
3. **Deterministic first.** Parsing, confidence, validation, decisions are plain Python. The LLM is a fallback
   extractor and an explainer. All LLM calls go through `llm/client.py`.
4. **Resume safety.** A LangGraph node that calls `interrupt()` re-runs from its first line on resume. So the
   interrupt lives in its own node, with no side effects before it. Every side effect uses the idempotency key
   `(run_id, step, item_id)` and is skipped if already done.
5. **Audit log is append-only.** INSERT only, SQLite triggers block UPDATE/DELETE, hash chain exactly as
   `AuditEntry.compute_hash()` defines. Provide a verifier.
6. **Never silently fix a number.** A changed value exists only as a recorded human decision.
7. **Money is `Decimal` in full units.** Apply "in millions/thousands" scale during extraction.
8. **Confidence uses extraction-time signals only.** Never ground truth.
9. **No secrets or data in git.** `.env`, `data/`, `*.db` are ignored.
10. **Every module ships with a test** in its owner's `tests/` folder. Resume and hash-chain tests are mandatory.

## 4. Defaults (live values are editable in the dashboard)

Confidence threshold 0.85 · YoY change 40% · accounting tolerance 0.1% · segment tolerance 0.1%.
A failed validation escalates every metric it names. Companies: AAPL, MSFT, TSLA, NVDA, AMZN.
Core metrics (8): revenue, net income, total assets, total liabilities, shareholders' equity, operating cash flow,
operating income, cash and equivalents. Optional: gross profit, diluted EPS.

## 5. Commands

```bash
uv sync
cp .env.example .env                       # set SEC_USER_AGENT
uv run uvicorn api.main:app --reload --port 8000
uv run streamlit run ui/app.py
uv run pytest
uv run ruff check . && uv run ruff format .
uv run python scripts/check_ownership.py   # before every PR
```

## 6. Git workflow

`main` is demo-ready only. `dev` is integration. Branch from `dev`: `feat/p1-<topic>`, `feat/p2-<topic>`,
`feat/p3-<topic>`. Prefixes `feat: fix: test: docs: chore:`. Small commits. PR into `dev` every 1-2 hours,
a teammate reviews. Rebase on `dev` first. `dev` merges to `main` at hours 10, 16, 21. Code freeze at hour 21.

## 7. Behaviour for AI agents

Smallest change that works. Ask before refactors. Run the relevant tests before saying done. Summarise changes in
three lines or fewer. Type hints, Pydantic at boundaries, ruff clean, functions under about 40 lines.

# Human-in-the-Loop Financial Filing Auditor Agent

MineArena 1.0 · PS-01 · Code Commit, BIET Davangere

An agent that extracts financial metrics from real SEC 10-K filings, validates them, auto-approves
what it is sure about, and **pauses for a human** on anything doubtful. Every human decision lands in
a tamper-evident audit log. See [`VISION.md`](VISION.md) for the why.

## How it works

```
fetch_filing -> extract -> score -> validate -> decide
                                                  |
                          all auto-approved ------+------ flagged values
                                  |                              |
                                  |                     review_gate (pause)
                                  |                              |
                                  +------------ apply_decisions -+
                                                  |
                                      verify vs XBRL -> accuracy report
```

- **Extraction** reads the filing's HTML tables with a deterministic parser and a label alias map.
- **Second reader (optional):** the LLM sees only the located statement rows and returns printed cell text. Agreement
  with the parser is the `extractor_agreement` confidence signal; a value only the model found is capped at 0.70.
- **Confidence** is a parse-quality score from six fixed signals (`label_match`, `unit_clarity`, `period_clarity`,
  `numeric_wellformed`, `table_type`, `extractor_agreement`) — not a model's opinion, never XBRL.
- **Traffic light**: Green = high confidence *and* every check passed (auto-approved); Yellow = medium confidence or
  a warning; Red = failed accounting rule, missing value, or very low confidence (the report is blocked until resolved).
- **The LLM has two call sites:** `explain_anomaly` (the plain-English reason on a failed check, with a
  deterministic fallback) and the optional second reader above. Both go through `llm/client.py`.
- **Ground truth** (SEC XBRL Company Facts) is used only for final verification, never for extraction.
- **Pause/resume** uses LangGraph `interrupt` + a SQLite checkpointer. Resumed runs repeat no side effects.
- **Audit log** is append-only and SHA-256 hash-chained.

## Stack

Python 3.11 · uv · LangGraph · FastAPI · React 18 + Vite + TypeScript · SQLite · httpx · selectolax · pandas · Pydantic v2 ·
Recharts · Ollama (local LLM) with Groq/Gemini free tiers as fallback.

## Quick start

```bash
# 1. Install uv (https://docs.astral.sh/uv/) then:
uv sync

# 2. Configure
cp .env.example .env        # set SEC_USER_AGENT="Your Name your@email.com"

# 3. Local LLM (optional if using Groq/Gemini)
ollama pull qwen2.5:7b

# 4. Run
uv run python scripts/prefetch.py           # pre-warm filings + XBRL for the 5 companies
uv run uvicorn api.main:app --reload --port 8000     # backend
cd trace-ui && npm install && npm run dev        # dashboard on :5173

# 5. Test
uv run pytest
cd trace-ui && npx playwright test       # reviewer journey against the running dashboard
```

## The database

PostgreSQL (Neon). The runs, the idempotency ledger, the LangGraph checkpoints and the
hash-chained audit log all live in one database; the filing and XBRL caches stay on disk in
`data/` because they are caches, not the database.

```bash
# .env
NEON_POOL_URL=postgresql://...@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
NEON_DIRECT_URL=postgresql://...@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
uv run python -m db.migrate          # create the tables (idempotent)
```

The app prefers the **direct** URL: the pooler adds a hop to every query (~1.2 s each), the
direct connection answers in ~50 ms. `Settings → Data store` shows the host, the latency and the
row counts, so the judge can see that the decisions are really stored.

## Two switches, one dashboard

The dashboard always runs against the real backend: SEC filing -> extraction -> validation ->
review -> XBRL verification. The sidebar badge says **Live data** and the settings page shows the
database it is talking to.

Fixture data is a stand-in while the workflow is being built: its accuracy report is trivially 100%
because the "answer key" is the extraction itself. Only **Live data** produces real numbers against
SEC XBRL facts.

## The dashboard (Person 3)

| Page | What it answers |
|---|---|
| Overview | what needs a human, how much was auto-approved, accuracy and escalation precision so far |
| New audit | pick a company, set the policy thresholds, start a run |
| Review queue | the flagged values of the newest run per company: value, tier, confidence signals, why it was escalated, the exact text from the filing, and Approve / Correct / Reject with a note |
| Filings | every company that has been audited, with its status and accuracy |
| Accuracy | final vs XBRL per company, per metric, and the calibration curve (confidence bucket -> share correct) |
| Audit log | the append-only, hash-chained decision log with a **Verify chain** button |
| Settings | policy thresholds (sliders, estimate, apply - every change is audited), data store, theme |

## Repo layout

One owner per folder. Only the owning person edits a folder; contract files are frozen for everyone.

| Folder | Contents | Owner |
|---|---|---|
| `extraction/` | EDGAR client, HTML parsers, `pipeline.py` (`fetch_filing`, `extract_filing`) | Person 1 |
| `llm/` | `client.py` (the single LLM entry point), `explain.py` | Person 1 |
| `mcp_server/` | MCP tool wrappers | Person 1 |
| `workflow/` | LangGraph graph + `service.py`, checkpointer, `fakes.py` | Person 2 |
| `audit/` | Append-only hash-chained log, verifier | Person 2 |
| `validation/` | `engine.py` (checks), `decide.py`, confidence scoring | Person 2 |
| `verification/` | XBRL ground truth, accuracy report, calibration | Person 3 |
| `api/` | FastAPI app, schemas at the boundary | Person 3 |
| `trace-ui/` | React reviewer dashboard (Vite, TypeScript) | Person 3 |
| `docs/` | Architecture, `docs/requests/` hand-off notes | Person 3 |
| `shared/` | `schemas.py`, `interfaces.py`, `config.py` (frozen contracts) | all |
| `tests/` | Mirror of the owner folders (`tests/extraction/`, `tests/workflow/`, ...) | each owner |
| `scripts/` | `check_ownership.py` and other team checks | all |
| `data/` | Cached filings and DBs (gitignored) | none |

## Working with OpenCode

Three role agents are defined in `.opencode/agent/`. Start OpenCode in the repo, then press **Tab**
to switch between `person1`, `person2`, `person3` (or launch with `opencode --agent person2`).
Each agent knows its folders, task list, and rules from `AGENTS.md`.

| Agent | Role | Owns |
|---|---|---|
| `person1` | Data extraction | `extraction/`, `llm/`, `mcp_server/` |
| `person2` | Workflow engine, trust layer | `workflow/`, `audit/`, `validation/` |
| `person3` | Verification, API, reviewer experience | `verification/`, `api/`, `trace-ui/`, `docs/` |

Nobody imports a teammate's module directly. Every cross-folder call goes through
`load_provider("<name>")` from `shared/interfaces.py`, so an unfinished module can be swapped for a fake.

## Git workflow

- `main` is release-ready only. `dev` is the integration branch.
- Branch from `dev`: `feat/p1-...`, `feat/p2-...`, `feat/p3-...`
- Small commits (`feat:`, `fix:`, `test:`, `docs:`). PR into `dev` every 1-2 hours, teammate reviews.
- Merge `dev` into `main` at hours 10, 16, and 21. Code freeze at hour 21.

## Timeline (24h)

| Hours | Goal |
|---|---|
| 0-1 | Agree on schemas in `shared/`, create repo, everyone builds against mocks |
| 1-8 | Parallel build: graph with fake nodes, Apple extraction, dashboard on the API |
| 8-10 | First end-to-end run on one company |
| 10-16 | 5 companies, confidence + validation, audit log, kill-and-resume test |
| 16-20 | Accuracy report, calibration chart, fault injection, adaptive thresholds |
| 20-23 | Bug fixes, freeze at 21, rehearse 3x, record backup video |
| 23-24 | Slides and final checks |

## Run checklist

- [ ] Pre-warm cache for all 5 companies (`scripts/prefetch.py`)
- [ ] Ollama running with `OLLAMA_KEEP_ALIVE=1h`
- [ ] Fault injection exercised
- [ ] Kill-and-resume rehearsed

## Known limits (we say these out loud)

5 companies, 8 to 10 metrics, HTML filings only, segment validation only where the filing has a
segment table.

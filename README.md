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

Python 3.11 · uv · LangGraph · FastAPI · Streamlit · SQLite · httpx · selectolax · pandas · Pydantic v2 ·
Plotly · Ollama (local LLM) with Groq/Gemini free tiers as fallback.

## Quick start

```bash
# 1. Install uv (https://docs.astral.sh/uv/) then:
uv sync

# 2. Configure
cp .env.example .env        # set SEC_USER_AGENT="Your Name your@email.com"

# 3. Local LLM (optional if using Groq/Gemini)
ollama pull qwen2.5:7b

# 4. Run
uv run uvicorn api.main:app --reload --port 8000     # backend
uv run streamlit run ui/app.py                       # dashboard (new terminal)

# 5. Test
uv run pytest
```

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
| `api/` | FastAPI app, schemas at the boundary, `mock_service.py` | Person 3 |
| `ui/` | Streamlit reviewer dashboard | Person 3 |
| `demo/` | Fault injection, prefetch, demo helpers, backup recording | Person 3 |
| `docs/` | Architecture, demo script, `docs/requests/` hand-off notes | Person 3 |
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
| `person3` | Verification, API, reviewer experience | `verification/`, `api/`, `ui/`, `demo/`, `docs/` |

Nobody imports a teammate's module directly. Every cross-folder call goes through
`load_provider("<name>")` from `shared/interfaces.py`, so an unfinished module can be swapped for a fake.

## Git workflow

- `main` is demo-ready only. `dev` is the integration branch.
- Branch from `dev`: `feat/p1-...`, `feat/p2-...`, `feat/p3-...`
- Small commits (`feat:`, `fix:`, `test:`, `docs:`). PR into `dev` every 1-2 hours, teammate reviews.
- Merge `dev` into `main` at hours 10, 16, and 21. Code freeze at hour 21.

## Timeline (24h)

| Hours | Goal |
|---|---|
| 0-1 | Agree on schemas in `shared/`, create repo, everyone builds against mocks |
| 1-8 | Parallel build: graph with fake nodes, Apple extraction, dashboard on mock API |
| 8-10 | First end-to-end run on one company |
| 10-16 | 5 companies, confidence + validation, audit log, kill-and-resume test |
| 16-20 | Accuracy report, calibration chart, fault injection, adaptive thresholds |
| 20-23 | Bug fixes, freeze at 21, rehearse 3x, record backup video |
| 23-24 | Slides and final checks |

## Demo checklist

- [ ] Pre-warm cache for all 5 companies (`demo/prefetch.py`)
- [ ] Ollama running with `OLLAMA_KEEP_ALIVE=1h`
- [ ] Backup recording ready
- [ ] Fault injection button tested
- [ ] Kill-and-resume rehearsed

## Known limits (we say these out loud)

5 companies, 8 to 10 metrics, HTML filings only, segment validation only where the filing has a
segment table.

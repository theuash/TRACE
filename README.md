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

- **Extraction** reads the filing's HTML tables. An LLM is used only as a fallback.
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
uv run uvicorn agent.api:app --reload --port 8000    # backend
uv run streamlit run ui/app.py                       # dashboard (new terminal)

# 5. Test
uv run pytest
```

## Repo layout

```
agent/        LangGraph workflow, API, audit log          (Person 1)
extraction/   EDGAR client, parsers, LLM fallback         (Person 2)
validation/   Confidence, checks, decisions, XBRL verify  (Person 2)
ui/           Streamlit reviewer dashboard                (Person 3)
demo/         Fault injection, prefetch, demo helpers     (Person 3)
shared/       Schemas, config, llm_client (team-owned)
docs/         Architecture, demo script
tests/        pytest suites
data/         Cached filings and DBs (gitignored)
```

## Working with OpenCode

Three role agents are defined in `.opencode/agent/`. Start OpenCode in the repo, then press **Tab**
to switch between `person1`, `person2`, `person3` (or launch with `opencode --agent person2`).
Each agent knows its folders, task list, and rules from `AGENTS.md`.

| Agent | Role |
|---|---|
| `person1` | Workflow, resume, API, audit log |
| `person2` | EDGAR, extraction, confidence, validation, XBRL accuracy |
| `person3` | Dashboard, demo, fault injection, docs |

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

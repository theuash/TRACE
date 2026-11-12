# Human-in-the-Loop Financial Filing Auditor Agent

MineArena 1.0 · PS-01 · Code Commit, BIET Davangere

An agent that extracts financial metrics from real SEC 10-K filings, validates them, auto-approves what it is sure
about, and **pauses for a human** on anything doubtful. Every human decision lands in a tamper-evident audit log.
See [`VISION.md`](VISION.md) for the why.

## Pipeline

```
fetch_filing -> extract -> score -> validate -> decide
                                                  |
                          all auto-approved ------+------ flagged values
                                  |                              |
                                  |                     review_gate (pause)
                                  |                              |
                                  +------------ apply_decisions -+
                                                  |
                                      verify vs XBRL -> report
```

Extraction reads the filing's HTML tables (LLM only as fallback). XBRL Company Facts is used **only** for verification.
Pause/resume uses LangGraph `interrupt` with a SQLite checkpointer. The audit log is append-only and SHA-256 hash-chained.

## Stack

Python 3.11 · uv · LangGraph · FastAPI · Streamlit · SQLite · httpx · selectolax · pandas · Pydantic v2 · Plotly ·
Ollama (local LLM) with Groq/Gemini free tiers as fallback.

## Quick start

```bash
uv sync
cp .env.example .env        # set SEC_USER_AGENT="Your Name your@email.com"
ollama pull qwen2.5:7b      # optional if using Groq/Gemini
bash scripts/install_hooks.sh
uv run uvicorn api.main:app --reload --port 8000    # backend
uv run streamlit run ui/app.py                      # dashboard (new terminal)
uv run pytest
```

## Who owns what

| Person | Role | Folders |
|---|---|---|
| 1 | Data extraction | `extraction/` `llm/` `mcp_server/` |
| 2 | Workflow engine, trust layer | `workflow/` `audit/` `validation/` |
| 3 | Verification, API, reviewer UI | `verification/` `api/` `ui/` `demo/` `docs/` |
| all | Frozen contracts | `shared/` (schemas, config, interfaces) |

Each person has a matching tests folder (`tests/<folder>/`). Nobody edits another person's folder; needs go in
`docs/requests/`. Teammates call each other only through `load_provider(...)`, and each person has a fake/mock
(`USE_FAKES`, `USE_MOCK_SERVICE`) so nobody is blocked.

## Working with OpenCode

Run `opencode` from the repo root. Press **Tab** to pick `person1`, `person2` or `person3`
(or `opencode --agent person2`). `AGENTS.md` and `VISION.md` load automatically for every agent.
Do not run `/init`: it would overwrite `AGENTS.md`.

## Git workflow

`main` is demo-ready only; `dev` is integration. Branch from `dev` as `feat/p1-...`, `feat/p2-...`, `feat/p3-...`.
Small commits (`feat:` `fix:` `test:` `docs:` `chore:`). PR into `dev` every 1-2 hours with a teammate review.
Run `uv run python scripts/check_ownership.py` before each PR. Merge `dev` into `main` at hours 10, 16 and 21.
Code freeze at hour 21. Dependency changes go in a tiny `chore/deps-<name>` branch; contract changes in `contract/<topic>`.

## Timeline (24h)

| Hours | Goal |
|---|---|
| 0-1 | Repo, `shared/` contracts reviewed, `.env` set, everyone on `dev` |
| 1-3 | P1 Apple extraction + fixture, P2 graph on fakes, P3 mock service + dashboard scaffold |
| 3-8 | P1 all tables/confidence, P2 resume + audit + validation, P3 review queue + XBRL verification |
| 8-10 | First end-to-end run on one company (`USE_FAKES=false`) |
| 10-16 | 5 companies, kill-and-resume test, scoreboard |
| 16-20 | Fault injection, calibration chart, adaptive thresholds |
| 20-23 | Bug fixes, freeze at 21, rehearse 3x, record backup video |
| 23-24 | Slides and final checks |

## Known limits (we say these out loud)

5 companies, 8 to 10 metrics, HTML filings only, segment validation only where the filing has a segment table.

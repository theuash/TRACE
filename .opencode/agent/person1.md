---
description: PERSON 1 - Data extraction (EDGAR, parsing, LLM fallback, confidence)
mode: primary
temperature: 0.1
# Optional hard lock (needs a recent OpenCode). Uncomment to make edits outside your folders denied:
# permission:
#   edit:
#     "*": deny
#     "extraction/**": allow
#     "llm/**": allow
#     "mcp_server/**": allow
#     "tests/extraction/**": allow
#     "tests/llm/**": allow
#     "tests/fixtures/**": allow
#     "docs/requests/**": allow
---
You are working with **Person 1: Data Extraction**. Read `AGENTS.md` and `VISION.md` first.

## You own (edit only these)
`extraction/`, `llm/`, `mcp_server/`, `tests/extraction/`, `tests/llm/`, `tests/fixtures/`

## You never edit
`workflow/`, `audit/`, `validation/` (Person 2) · `verification/`, `api/`, `ui/`, `demo/`, `docs/` (Person 3) ·
`shared/` (frozen). Before each edit confirm the path is yours. Otherwise write `docs/requests/p1-to-pX-<topic>.md`.

## What you deliver (exact names, see `shared/interfaces.py`)
- `extraction.pipeline.fetch_filing(company: Company) -> FilingRef`  (cache-first, SEC User-Agent, rate limited)
- `extraction.pipeline.extract_filing(filing: FilingRef) -> ExtractionResult`
- `extraction.confidence.score_extraction(result: ExtractionResult) -> ExtractionResult`
- `llm.explain.explain_anomaly(validation, metric) -> str`  (never raises; deterministic fallback text)
- `llm.client.complete_json(...)` and `complete_text(...)`, backed by one OpenAI-compatible client for Ollama/Groq/Gemini.

## Your mission
Make the numbers **correct** and the confidence **honest**. Extraction accuracy and confidence quality are the top two
judging criteria, and everything downstream depends on your output.

## Order of work
1. Smoke test: fetch Apple's `Assets` from Company Facts, only to confirm SEC access and headers work. Never in extraction.
2. `extraction/edgar.py`: CIK to latest 10-K, download the primary HTML, cache in `data/filings/`.
3. `extraction/locate.py`: find the balance sheet, income statement and cash flow tables; read the scale ("in millions").
4. `extraction/table_parser.py`: exact then fuzzy label matching, current AND prior year columns, `SourceEvidence`
   with `matched_text` the UI can highlight. Use `selectolax` and `pandas.read_html`.
5. **Save real parsed Apple output as `tests/fixtures/aapl_extraction.json` by hour 3.** P2 and P3 mock against it.
6. `extraction/segments.py`: segment tables for the segment-sum check, where the filing has one.
7. `extraction/confidence.py`: weighted extraction-time signals (parser/LLM agreement, label match quality, unit and
   period clarity, statement section). Store each signal in `confidence_signals`.
8. `llm/client.py` and `extraction/llm_fallback.py`: only for unclear tables; send only the table text; force JSON
   and validate with Pydantic. Keep the model warm (`OLLAMA_KEEP_ALIVE=1h`).
9. Scale to all 5 companies; add one fixture per company. Amazon has no "Total liabilities" line: derive by summing
   components, mark `Extractor.DERIVED`, give lower confidence.
10. `llm/explain.py`, then (stretch) `mcp_server/` exposing `fetch_filing` and XBRL lookup as MCP tools.

## Definition of done
8+ metrics per company for 5 companies with period, unit, scale, evidence; prior-year values; fixtures committed;
tests for parsing and confidence; extraction never imports anything from `verification/`.

Branches: `feat/p1-<topic>`. Run `uv run python scripts/check_ownership.py` before every PR.

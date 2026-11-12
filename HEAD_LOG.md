# HEAD_LOG

Append-only record of rule and contract changes. Newest last.

## 2026-11-12 — hybrid extractor (parser primary, LLM second reader)

**Changed**

- `AGENTS.md` rule 3: the LLM may act as a **second reader** in extraction. It never retrieves filings,
  never supplies the only copy of a value above confidence 0.70, never decides a tier.
- `VISION.md` "Where the LLM sits": rewritten to describe both call sites.
- `README.md`: two bullets that claimed extraction has no LLM.

**Why** — the human asked for parser/LLM agreement as the confidence signal. The frozen schema already
carried `Extractor.LLM` and `Extractor.BOTH`, so no `shared/` change was needed; only the prose.

**Nothing else moves:** six confidence signal names unchanged, `confidence_signals` shape unchanged,
`PROVIDERS`/`FAKES` unchanged, no new field in any schema.

**Who must restart OpenCode:** person1, person2, person3 — all three load `AGENTS.md` at session start.
Person 2 and Person 3 need no code change; `extractor` may now be `llm` or `both` in the data they read.

**Also on this date (Person 1 build, no rule impact)**

- `extraction/` + `llm/` implemented: `http.py`, `edgar.py`, `locate.py`, `table_parser.py`,
  `confidence.py`, `segments.py`, `pipeline.py`, `__main__.py`, `llm/client.py`, `llm/explain.py`,
  `llm/second_reader.py`.
- Fixtures generated for AAPL and MSFT (`tests/fixtures/*_extraction.json`). TSLA/NVDA/AMZN need a real
  `SEC_USER_AGENT` in `.env` plus network access.
- 47 tests, all offline. `python -m extraction --fixture TICKER` regenerates a fixture.

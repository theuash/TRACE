# Person 1 — Data Extraction: Build Plan

Owner: Person 1. Folders: `extraction/`, `llm/`, `mcp_server/`, `tests/extraction/`, `tests/llm/`,
`tests/fixtures/`.
This file lives in `extraction/` because `docs/` belongs to Person 3. Nothing here is a contract
change; every signature already exists in `shared/interfaces.py`.

> Mission in one line: make the numbers **correct** and the confidence **honest**.
> Extraction reads the 10-K HTML. XBRL is P3's answer key and is never imported here.

---

## 1. What the rest of the team expects from me

| Provider name | Module path | Signature |
|---|---|---|
| `fetch_filing` | `extraction.pipeline:fetch_filing` | `(company: Company) -> FilingRef` |
| `extract_filing` | `extraction.pipeline:extract_filing` | `(filing: FilingRef) -> ExtractionResult` |
| `score_extraction` | `extraction.confidence:score_extraction` | `(result: ExtractionResult) -> ExtractionResult` |
| `explain_anomaly` | `llm.explain:explain_anomaly` | `(validation, metric) -> str` |
| (internal) | `llm.client:complete_json` / `complete_text` | one OpenAI-compatible client |

Hard rules I must not break:

1. Cache-first, then network. `SEC_USER_AGENT` on every request. Max 8 req/s, same-filing twice = zero
   network calls.
2. No LLM in fetch or extract. The only model call in the whole system is `explain_anomaly`.
3. `extraction/` must not import `verification/`, `validation/`, `workflow/` or `audit/`. Only
   `shared/`. (I may grep for this before every PR.)
4. Money is `Decimal` in **full units**: the printed scale ("in millions") is applied once, inside
   extraction, and the multiplier is kept in `ExtractedMetric.scale`.
5. `confidence` is computed from six extraction-time signals only. Same filing → same score, every run.

---

## 2. Module map

```
extraction/
  __init__.py
  http.py          # one shared httpx client: UA header, throttle, disk cache  (small, used by edgar)
  edgar.py         # CIK -> latest 10-K -> primary HTML on disk; FilingRef cache
  locate.py        # find balance sheet / income statement / cash flow table + scale + periods
  table_parser.py  # label aliases, row -> raw text cells, prior+current columns, evidence
  segments.py      # segment table -> SegmentTable (only where the filing has one)
  confidence.py    # six signals + fixed weights + score_extraction
  pipeline.py      # fetch_filing, extract_filing (orchestration only)
  __main__.py      # python -m extraction --fixture AAPL  -> tests/fixtures/aapl_extraction.json

llm/
  __init__.py
  client.py        # complete_text, complete_json  (Ollama / Groq / Gemini via base_url + key)
  explain.py       # explain_anomaly: prompt + deterministic fallback, never raises

mcp_server/
  server.py        # stretch: expose fetch_filing (+ extract_filing) as MCP tools
```

Nothing else. No `extraction/fallback_llm.py` unless there is spare time (see §8).

---

## 3. Workflow A — `fetch_filing`

```
Company(ticker, cik)
  |
  | 1. cache? data/filings/{TICKER}_filingref.json  -> return FilingRef, 0 HTTP
  | 2. GET data.sec.gov/submissions/CIK{cik}.json   (cached: data/edgar/submissions_{cik}.json)
  | 3. pick newest filings.recent[] where form == "10-K"
  | 4. GET https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{primaryDocument}
  |    -> data/filings/{TICKER}_{accession}.htm
  | 5. build + persist FilingRef (local_path set)
  v
FilingRef
```

Details that matter:

- **Cache key** is the ticker, not the accession, because the accession is only known after the
  submissions call. `filingref.json` is written only after the HTML is on disk, so a half-download can
  never poison the cache. A stale cache is fine: the latest 10-K changes once a year. Force refresh =
  delete the file (documented, not a setting).
- **`fiscal_year`** = `period_end.year` if `period_end.month >= 6`, else `period_end.year`. NVDA's
  January year-end therefore maps to the year the company calls FY20xx. P3 matches XBRL on
  *accession + period_end*, so this stays a labelling choice, not a cross-team risk.
- **Rate limit**: one monotonic gate, `sleep` until `1/sec_max_rps` (default 8/s → 0.13s floor;
  I use 0.2s) between requests. One `httpx.Client(timeout=60, follow_redirects=True)` with
  `User-Agent: settings.sec_user_agent` and `Accept-Encoding: gzip, deflate`.
- **`assert_sec_user_agent()`** runs before the first request. A 403 becomes a `RuntimeError` that
  names `.env` and `SEC_USER_AGENT`, never a bare traceback.
- Async is not needed: P2 calls this from the graph; it returns `FilingRef` in well under a second
  from cache. Keep the signature sync as the Protocol says.

Failure modes and behaviour: no 10-K in submissions → `RuntimeError`; network down but HTML cached →
still returns; network down and no cache → raise (the run must fail loudly, not invent data).

---

## 4. Workflow B — `extract_filing`

```
FilingRef.local_path (HTML)
  |
  locate.detect_statements(html)
     -> {balance_sheet, income_statement, cash_flow}: {table_index, node, scale, periods[]}
  |
  table_parser.read_rows(table, scale, periods)
     -> rows: [{label_raw, cells: [{raw_text, value, is_current}], matched_text}]
  |
  for metric in CORE_METRICS + OPTIONAL_METRICS:
     metric -> preferred statement -> alias match (exact | regex | suffix)
        -> ExtractedMetric(current col)  +  ExtractedMetric(prior col) into prior_metrics
  |
  second pass with pandas.read_html on the same table -> extractor_agreement signal
  |
  segments.find_segment_table(html) -> SegmentTable | []
  |
  ExtractionResult(filing, metrics, prior_metrics, segments, warnings)
```

### 4.1 `locate.py`

- Parse with `selectolax`. Walk `table` nodes; score each candidate by
  (a) keywords in the table's own text and the ~40 words of text immediately before it,
  (b) presence of 2+ known row labels from that statement's alias set,
  (c) at least 6 rows with one label cell and one or more numeric cells.
- Keyword sets: balance sheet = `balance sheet` + `total assets`; income = `statements of operations`
  / `income statement` / `total revenues` / `net income`; cash flow = `cash flows` +
  `operating activities`. Highest score wins per type; the two runner-ups go into
  `ExtractionResult.warnings` so a wrong pick is visible.
- **Scale** = regex over the caption row and the 6 lines of text before the table:
  `in thousands` → 1_000, `in millions` → 1_000_000. The whole-document default is "in millions";
  a table with no scale header gets `scale=1_000_000` but `unit_clarity` drops (see §6).
- **Periods**: header cells holding `September 27, 2025` / `Sep. 27, 2025` / `2025` →
  `datetime.date`. Column order decides current vs prior: the first date column is the current
  fiscal year, the second becomes `prior_metrics`. If a header cell cannot be dated, period_clarity
  drops and the column is still used positionally.

### 4.2 `table_parser.py`

- Row = one `<tr>`; label = first non-empty text cell; the remaining cells are values.
- Cell normalisation, in this order: strip `&nbsp;`, whitespace, `$`, `,`; `—`/`–`/`-` alone → `0`
  (numeric_wellformed penalty); `(123)` → `-123`; strip trailing footnote markers `(1)`, `(a)`,
  `*`; a cell with two numbers or a range is rejected (`raw_text` kept, `numeric_wellformed` low).
- `raw_text` is always **exactly as printed** (e.g. `"352,583"`). `value` is
  `Decimal(raw) * scale`. `matched_text` is that same printed string, so the UI highlight is a real
  substring of `snippet`.
- `SourceEvidence.snippet` = `f"{label_raw} | {raw_1} | {raw_2}"` of that row;
  `location` = `f"{statement_name}, row {label_raw!r}"`; `table_index` = index into the document's
  tables; `source_url` = `FilingRef.url`.
- **Label matching, three tiers** (this *is* the `label_match` signal):

| Tier | Rule | `label_match` |
|---|---|---|
| exact | normalised row label equals an alias (`total shareholders' equity` == alias) | 1.0 |
| regex | alias regex after normalisation (lowercase, collapse spaces, strip `$`, drop trailing `:` and footnote refs) | 0.85 |
| suffix/contains | alias is a suffix of the label, e.g. `Total assets` inside `Total assets (1)` | 0.7 |
| none | no row | metric missing, goes to `warnings` |

- Alias sets live in one dict `ALIASES: dict[Metric, tuple[str, ...]]` at the top of the file — the
  only tunable place. Minimum set (extended per company after the first real run):

| Metric | Aliases (ordered, most specific first) |
|---|---|
| revenue | `total net sales`, `total revenues`, `total revenue`, `net sales`, `revenues` |
| net_income | `net income`, `net income (loss)`, `net earnings`, `net loss` |
| operating_income | `operating income`, `income from operations`, `operating profit` |
| gross_profit | `gross profit`, `gross margin` |
| total_assets | `total assets` |
| total_liabilities | `total liabilities` |
| shareholders_equity | `total shareholders' equity`, `total stockholders' equity`, `total equity`, `total shareholders\u2019 equity` |
| operating_cash_flow | `net cash provided by operating activities`, `net cash provided by (used in) operating activities`, `cash generated by operating activities` |
| cash_and_equivalents | `cash and cash equivalents` (balance sheet, **not** the cash-flow ending-balance line) |
| diluted_eps | `diluted earnings per share` (unit `USD/share`, scale 1, never multiplied) |

- Metric → statement preference: assets/liabilities/equity/cash → balance sheet; revenue/net
  income/operating income/gross profit/EPS → income statement; operating cash flow → cash flow.
  Fallback: search the other two statements, and record a `warnings` entry plus a `table_type`
  penalty (a revenue row found in a note table must not look clean).
- **AMZN `total_liabilities`**: try the alias list first. If absent (likely), derive
  `total_assets - shareholders_equity`, set `extractor=DERIVED`, and `confidence` is capped at 0.80
  in `confidence.py`, below the 0.85 green line, so it always gets eyes. If equity is missing too,
  derive from `total current liabilities + total non-current liabilities` when both rows exist.
  No derivation → metric missing, `warnings` entry, P2's `decide` escalates it.

### 4.3 Second extractor (no LLM)

`pandas.read_html(html)` over the located table gives a second, independent read of the same cells.
It is not a fallback extractor; it exists only to produce `extractor_agreement`:
compare `(normalised label, Decimal value)` pairs; equal → 1.0, one cell apart → 0.6, different →
0.3, pandas failed to read the table → 0.5 (neutral, not punished for a library quirk).

### 4.4 `segments.py`

Only if the filing has a segment table (revenue by segment / by geography) in `Note` sections:
label+value rows, `reported_total` from a `total` row or the revenue metric, `total_metric=REVENUE`,
one `SegmentTable` per fiscal year found. No table → empty list, and P2's segment check reports
"not applicable" instead of failing. Guard against double counting: skip rows whose label is
`total`, `eliminations` goes into the list as a signed value only if printed signed.

---

## 5. Workflow C — `score_extraction`

Deterministic. Reads only fields that extraction already wrote. No network, no XBRL, no model.

| Signal | 0.0 | 1.0 | Source |
|---|---|---|---|
| `label_match` | no/suffix guess 0.7 | exact alias 1.0 | parser tier |
| `table_type` | stray note table 0.2 | a located financial statement 1.0 | locate score |
| `unit_clarity` | no scale anywhere 0.3 | explicit "in millions" header 1.0 | locate scale |
| `period_clarity` | column header unparsed 0.4 | column maps to the current period_end 1.0 | header parse |
| `numeric_wellformed` | range/footnote/merged 0.4 | one clean number 1.0 | cell normaliser |
| `extractor_agreement` | primary and pandas disagree 0.3 | both read the same value 1.0 | §4.3 |

Weights (fixed, sum 1.0): `label_match .25`, `numeric_wellformed .20`, `unit_clarity .15`,
`period_clarity .15`, `table_type .15`, `extractor_agreement .10`.

```
confidence = round(sum(w_i * s_i), 4)
if extractor == DERIVED:  confidence = min(confidence, 0.80)
```

Every signal is stored in `metric.confidence_signals`, so the calibration chart (P3) can show *why*
a bucket is inaccurate. Clean Apple row: `1.0*.25 + 1.0*.20 + 1.0*.15 + 1.0*.15 + 1.0*.15 + 1.0*.10
= 1.00`. Missing scale header + suffix label guess: `0.25*0.7 + 0.20 + 0.15*0.3 + 0.15 + 0.15 + 0.10
= 0.775` → Yellow. That is the intended shape: boring rows are green, suspicious rows are not.

`score_extraction` returns a copy with `confidence` and `confidence_signals` filled
(`model_copy(update=...)` on each metric), and is idempotent — scoring twice gives the same numbers,
which the test asserts.

---

## 6. Workflow D — LLM layer (one function, one client)

`llm/client.py`

```python
complete_text(prompt, *, system=None, model=None, json_mode=False, max_tokens=300) -> str
complete_json(prompt, *, system=None, model=None, max_tokens=300) -> dict[str, Any]
```

- One `openai.OpenAI(base_url=..., api_key=...)` built from
  `settings.llm_base_url_and_key()`, so Ollama/Groq/Gemini differ only by `.env`.
- `json_mode` sets `response_format={"type": "json_object"}`, then falls back to slicing the first
  `{...}` block if the provider ignored it. `complete_json` raises `ValueError` on unparseable output;
  the caller decides.
- `timeout=settings.llm_timeout_s`, `temperature=0`. The client may raise; that is fine — only
  `explain_anomaly` promises never to raise.

`llm/explain.py`

```
explain_anomaly(validation, metric) -> str
  prompt = check name + detail + expected/actual/difference_pct
         + metric label/value/raw_text/evidence.location
  -> complete_text(..., model=settings.llm_model_explain, max_tokens=120)
  -> strip, collapse whitespace, enforce one or two sentences
  except Exception -> _fallback(validation, metric)
```

`_fallback` is a pure template per check: e.g.
`"Accounting equation check failed: assets were read as 352,583M against liabilities + equity of
352,9xxM; the difference is 0.4%. The value may have been misread from the filing."`
It uses only numbers already in the `ValidationResult`, so it is safe offline and deterministic.
An in-process `lru_cache` keyed on a canonical json of (check, detail, metric id, value) avoids a
duplicate call inside one run; cross-process caching stays P2's job (`decide` caches the explanation).

Never: explain to *change* a number, explain to *decide* a tier, or retry a failed check.

---

## 7. Tests (all in my folders)

| File | Asserts |
|---|---|
| `tests/extraction/test_label_match.py` | exact / regex / suffix tiers map to 1.0 / .85 / .7; AMZN-style labels hit |
| `tests/extraction/test_table_parser.py` | tiny inline HTML: `(1,234)` → `-1234`, `—` → 0, footnote stripped, scale applied, raw_text preserved, prior column captured |
| `tests/extraction/test_locate.py` | picks balance sheet over a note table; reads "in millions"; dates the columns |
| `tests/extraction/test_confidence.py` | same input twice → identical score; DERIVED ≤ 0.80; missing scale lowers the score; clean row = 1.0 |
| `tests/extraction/test_edgar.py` | cache hit makes zero HTTP calls (monkeypatched transport); `fiscal_year` rule; 403 raises the UA message |
| `tests/extraction/test_derived.py` | AMZN-style input without `total liabilities` → DERIVED value, capped confidence |
| `tests/extraction/test_segments.py` | segment rows sum to reported total; no table → `[]` |
| `tests/extraction/test_fixture.py` | `tests/fixtures/aapl_extraction.json` validates as `ExtractionResult`, 8+ metrics, prior year present |
| `tests/llm/test_explain.py` | client raising → fallback string, non-empty, no exception; success path returns one sentence |
| `tests/llm/test_client.py` | json_mode fallback parsing; provider/base_url wiring from settings |

Offline by default. One live test guarded by `SEC_LIVE=1` so CI and demos never need the network.

**Fixture (hour 3 deadline)**: `python -m extraction --fixture AAPL` writes
`tests/fixtures/aapl_extraction.json` (round-tripped through `ExtractionResult.model_dump_json`
so P2/P3 can `model_validate_json` it directly). One fixture per company by the end:
`aapl_`, `msft_`, `tsla_`, `nvda_`, `amzn_extraction.json`.

---

## 8. Order of work (and what "done" means at each step)

| Step | Branch | Deliverable | Done when |
|---|---|---|---|
| 0 | — | smoke: Company Facts `Assets` for AAPL, once, manually | SEC headers work (this is a one-off check, **never** imported into extraction) |
| 1 | `feat/p1-edgar` | `http.py`, `edgar.py`, `pipeline.fetch_filing` | AAPL 10-K HTML cached locally twice in a row with one network call |
| 2 | `feat/p1-tables` | `locate.py`, `table_parser.py` | AAPL balance sheet + income statement + cash flow parsed, current **and** prior year, values tagged |
| 3 | `feat/p1-confidence` | `confidence.py` | six signals on every metric, deterministic test green |
| 4 | `feat/p1-fixture` | `tests/fixtures/aapl_extraction.json` | fixture validates, 8+ metrics, P2/P3 unblocked |
| 5 | `feat/p1-segments` | `segments.py` | segment sum check has data for at least 2 companies |
| 6 | `feat/p1-llm` | `llm/client.py`, `llm/explain.py` | fallback proven with no Ollama running |
| 7 | `feat/p1-scale` | alias tuning for MSFT/TSLA/NVDA/AMZN | 8+ metrics × 5 companies, one fixture each, AMZN derived field capped at 0.80 |
| 8 | `feat/p1-mcp` (stretch) | `mcp_server/server.py` | tools list and call `fetch_filing` from an MCP client |

Each step: `uv run pytest tests/extraction tests/llm`, `uv run ruff check .`, then PR into `dev`.

---

## 9. Known risks / per-company traps

- **MSFT HTML is 8.6 MB** → `pandas.read_html` on the whole document is slow. Parse the located
  table node only, and cache parsed rows under `data/parsed/{ticker}_{acc}.json` keyed by file hash.
- **iXBRL inline markup** (`<ix:nonfraction>`) splits numbers into nested tags. Take cell text from
  the fully rendered cell, not the first child text node.
- **Apple** restated "net sales" vs "revenues" wording; alias order matters.
- **AMZN** has no `Total liabilities` → DERIVED per §4.2.
- **TSLA** uses `Total revenues` and a merged-header balance sheet; **NVDA** fiscal year ends in
  January, so the current column's `period_end` is next calendar year.
- **Two candidate tables** (statement + note) → highest locate score wins, the other lands in
  `warnings` so P2 can escalate rather than guess.
- Root `edgar.py` + `cache/` are scratch artefacts from the kickoff exploration, owned by nobody.
  Ask the team to delete them so two EDGAR clients cannot drift apart.

## 10. Handoffs

- **To P2**: `prior_metrics` is for YoY only; `segments` may be empty; DERIVED values cap at 0.80;
  `warnings` is a plain string list safe to display.
- **To P3**: every metric has `evidence.matched_text` that is a literal substring of
  `evidence.snippet` (click-to-highlight contract); confidence signals keyed by the six fixed names;
  fixtures are `ExtractionResult` JSON.
- **Open question for P3**: the brief mentions an "XBRL lookup MCP tool" on my side, but hard rule 1
  says only `verification/` may call Company Facts. Default: I ship `fetch_filing` + `extract_filing`
  tools only, and P3 can expose XBRL if they want it in the demo.

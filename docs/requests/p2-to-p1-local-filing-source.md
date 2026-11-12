# P2 -> P1: read filings from the local `data/form 10-K` folder

Asked by: HEAD on behalf of the human. Date: 2026-11-12.

## What is on disk right now

`data/form 10-K/` holds **114 EDGAR submission-index JSON files** (`CIK##########.json`). Each one is the
SEC "submissions" payload: `name`, `tickers`, `filings.recent` with `form`, `accessionNumber`,
`filingDate`, `reportDate`, `primaryDocument`.

- 405 10-K filings across those 114 companies, the newest `AAR CORP`, 2026-07-22
  (`0001104659-26-085459`, `air-20260531x10k.htm`).
- **No filing documents are stored, only the indexes.** So nothing can be extracted from this folder yet.
- None of the five configured demo companies (AAPL, MSFT, TSLA, NVDA, AMZN) is among those 114 CIKs.

SEC is reachable from this machine (200 on `www.sec.gov` with a User-Agent header), so the documents can
be downloaded once `SEC_USER_AGENT` is set in `.env`.

## What P1 needs to provide

1. **Cache-first local source.** `fetch_filing(company)` must resolve in this order:
   `data/filings/<CIK>/<primary_document>` -> EDGAR download -> store there. The `FilingRef.local_path`
   field already exists for this.
2. **Local index helper** (`extraction/locate.py` is the natural home):
   `resolve_latest_10k(cik) -> (accession_number, filing_date, report_date, primary_document, url)`
   reading `data/form 10-K/CIK##########.json` with no network. Returns `None` when the folder has no
   index for that CIK. This is what makes the demo runnable offline from a pre-warmed cache.
3. **One accepted HTML** is all P2/P3 need to start: a fixture-shaped JSON per company in `tests/fixtures/`
   (already in P1's task list) is enough for everyone else.

## What P2 promises in return

- P2 will not touch `extraction/`, `llm/`, or `tests/fixtures/`.
- `workflow/fakes.py` keeps the demo green until P1's first fixture lands; `USE_FAKES=false` flips the
  graph to the real parser with no code change on either side.
- P2's CLI (`python -m workflow.cli`) and P3's dashboard read `FilingRef` through the same contract, so
  swapping the source changes nothing downstream.

## Suggested first target

Drop `air-20260531x10k.htm` (or any one local HTML) into `data/filings/0000001750/` and show one
`FilingRef` + 8 metrics from it. P2 will wire the rest of the demo around whichever company P1 lands first.

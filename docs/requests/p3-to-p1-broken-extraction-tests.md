# P3 -> P1: five extraction tests error on missing fixtures

From: Person 3 · Date: 2026-11-12 · Branch: `feat/p3-api-verification`

## What fails

`uv run pytest` reports `83 passed, 3 skipped, 5 errors`. All five errors are setup errors in
`tests/extraction/` (yours) — no assertion ever runs:

| Test | Missing fixture |
|---|---|
| `test_edgar.py::test_cached_filing_ref_short_circuits` | `make_filing` |
| `test_locate.py::test_picks_the_statement_not_the_note` | `html_file` |
| `test_locate.py::test_reads_scale_and_periods` | `html_file` |
| `test_segments.py::test_segments_sum_to_the_reported_total` | `html_file`, `make_filing` |
| `test_segments.py::test_no_segment_table_gives_an_empty_list` | `html_file`, `make_filing` |

Neither `tests/conftest.py` (root) nor `tests/extraction/` defines `html_file` or `make_filing`.
`settings` exists (pytest's own), which is why only the other two show as missing.

## Suggested shape (your call, these are your folders)

```python
# tests/extraction/conftest.py
@pytest.fixture()
def html_file(tmp_path):
    def _write(body: str) -> Path: ...   # returns a path to a minimal 10-K-like HTML file

@pytest.fixture()
def make_filing(tmp_path):
    def _make(**overrides) -> FilingRef: ...  # points at the local html file, no network
```

Tests run with `USE_FAKES=true` and an isolated `DATA_DIR` from the root conftest, so a local
`FilingRef.local_path` keeps them offline.

## Why it matters to me

`progress.md` and any CI-style gate report the suite as red, and a first-time judge running
`uv run pytest` sees five errors before they see the demo. Everything else in the suite passes.

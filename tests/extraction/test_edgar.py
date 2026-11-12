from datetime import date

import pytest

from extraction import edgar, http
from shared.config import get_settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def boom(*args, **kwargs):
    raise AssertionError("network access in a test")


def test_cache_hit_never_touches_the_network(settings, monkeypatch):
    cache = settings.data_dir / "edgar" / "x.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text('{"ok": 1}', encoding="utf-8")
    monkeypatch.setattr(http, "get_client", boom)

    assert http.fetch_json("https://example.invalid/x.json", cache) == {"ok": 1}


def test_cached_filing_ref_short_circuits(settings, make_filing, monkeypatch):
    settings.ensure_dirs()
    html_path = settings.filings_dir / "AAPL_0000320193-26-000026.htm"
    html_path.write_text("<html></html>", encoding="utf-8")
    ref = make_filing(local_path=str(html_path))
    (settings.filings_dir / "AAPL_filingref.json").write_text(
        ref.model_dump_json(), encoding="utf-8"
    )
    monkeypatch.setattr(edgar.http, "fetch_json", boom)

    assert edgar.filing_ref(ref.company).accession_number == "0000320193-26-000026"


def test_newest_10k_ignores_amendments_and_older_forms():
    submissions = {
        "filings": {
            "recent": {
                "form": ["10-K/A", "10-Q", "10-K"],
                "accessionNumber": ["a", "b", "c"],
                "filingDate": ["2026-01-01", "2026-02-01", "2026-03-01"],
                "reportDate": ["2025-12-31", "2026-03-31", "2026-03-31"],
                "primaryDocument": ["x.htm", "y.htm", "z.htm"],
            }
        }
    }
    assert edgar.newest_10k(submissions)["accessionNumber"] == "c"


def test_january_year_end_is_labelled_with_its_own_year():
    assert edgar.fiscal_year(date(2026, 1, 25)) == 2026
    assert edgar.fiscal_year(date(2025, 9, 27)) == 2025

"""The SEC company directory: parse, rank and resolve without touching the network."""

from extraction import directory

RAW = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1065280, "ticker": "NFLX", "title": "NETFLIX INC"},
    "2": {"cik_str": 1326801, "ticker": "META", "title": "Meta Platforms, Inc."},
    "3": {"cik_str": 1090727, "ticker": "BAC-PB", "title": "BANK OF AMERICA CORP /DE/"},
    "4": {"cik_str": 1090728, "ticker": "BAC", "title": "BANK OF AMERICA CORP /DE/"},
    "bad": {"ticker": None, "title": "broken row"},
}
POOL = directory.parse_directory(RAW)


def test_parse_pads_the_cik_and_skips_broken_rows():
    assert [c.ticker for c in POOL] == ["AAPL", "NFLX", "META", "BAC-PB", "BAC"]
    assert directory._cik("320193") == "0000320193"


def test_search_finds_a_company_the_demo_does_not_ship_with():
    found = directory.search("netflix", directory=POOL)
    assert [c.ticker for c in found] == ["NFLX"]
    assert found[0].cik == "0001065280"


def test_search_prefers_common_stock_over_a_class_suffix():
    found = directory.search("bank of america", directory=POOL)
    assert [c.ticker for c in found] == ["BAC", "BAC-PB"]


def test_resolve_accepts_a_ticker_or_a_cik():
    assert directory.resolve("nflx", directory=POOL).cik == "0001065280"
    assert directory.resolve("1065280", directory=POOL).ticker == "NFLX"
    assert directory.resolve("0001065280", directory=POOL).ticker == "NFLX"
    assert directory.resolve("AAPL", directory=POOL).name == "Apple Inc."


def test_resolve_returns_none_for_an_unknown_company():
    assert directory.resolve("NOPE", directory=POOL) is None
    assert directory.resolve("", directory=POOL) is None

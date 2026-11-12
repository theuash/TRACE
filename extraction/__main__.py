"""python -m extraction --fixture AAPL   -> tests/fixtures/aapl_extraction.json

Gives Person 2 and Person 3 a real ExtractionResult to build against before the graph exists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from extraction import alias_memory
from extraction.pipeline import extract_filing, fetch_filing
from shared.config import COMPANIES, get_company, get_settings
from shared.schemas import ExtractionResult

FIXTURES = Path("tests/fixtures")


def build(ticker: str) -> ExtractionResult:
    company = get_company(ticker)
    return extract_filing(fetch_filing(company))


def dump(result: ExtractionResult, directory: Path = FIXTURES) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.filing.company.ticker.lower()}_extraction.json"
    path.write_text(json.dumps(json.loads(result.model_dump_json()), indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a 10-K and write a test fixture.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fixture", metavar="TICKER", help="one company, e.g. AAPL")
    group.add_argument("--all", action="store_true", help="all five configured companies")
    group.add_argument(
        "--aliases", action="store_true", help="labels the model taught the parser, then exit"
    )
    args = parser.parse_args()

    if args.aliases:
        known = alias_memory.known()
        if not known:
            print("No learned aliases yet. The parser has not needed the model.")
        for label, metric in sorted(known.items(), key=lambda kv: kv[1]):
            print(f"  {metric:22} <- {label!r}")
        return

    get_settings().ensure_dirs()
    tickers = [company.ticker for company in COMPANIES] if args.all else [args.fixture]
    for ticker in tickers:
        result = build(ticker)
        path = dump(result)
        print(f"{ticker}: {len(result.metrics)} metrics -> {path}")
        for warning in result.warnings:
            print(f"  ! {warning}")


if __name__ == "__main__":
    main()

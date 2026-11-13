"""Pre-warm the caches the pipeline needs, so a run works offline.

    uv run python scripts/prefetch.py              # filings + XBRL for all five companies
    uv run python scripts/prefetch.py --xbrl       # XBRL answer key only
    uv run python scripts/prefetch.py AAPL MSFT    # only these tickers

SEC etiquette: every request carries SEC_USER_AGENT and stays under 8 req/s (see
`shared/config.py`). Cached entries are skipped, so re-running costs zero network calls.
"""

from __future__ import annotations

import argparse

from shared.config import COMPANIES, get_settings
from shared.interfaces import load_provider


def prefetch_filing(ticker: str) -> str:
    company = next(c for c in COMPANIES if c.ticker == ticker)
    ref = load_provider("fetch_filing")(company)
    return f"{ticker}: filing cached at {ref.local_path or ref.url}"


def prefetch_xbrl(ticker: str) -> str:
    from verification import xbrl_client

    company = next(c for c in COMPANIES if c.ticker == ticker)
    payload = xbrl_client.fetch_company_facts(company.cik)
    facts = len(payload.get("facts", {}).get("us-gaap", {}))
    return f"{ticker}: XBRL cached ({facts} concepts)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-warm the filing and XBRL caches.")
    parser.add_argument("--xbrl", action="store_true", help="only the XBRL answer key")
    parser.add_argument("--tickers", nargs="*", default=[c.ticker for c in COMPANIES])
    args = parser.parse_args()

    get_settings().ensure_dirs()
    for ticker in args.tickers:
        if not args.xbrl:
            print(prefetch_filing(ticker))
        print(prefetch_xbrl(ticker))
    print("Done. The pipeline can now run offline from data/.")


if __name__ == "__main__":
    main()

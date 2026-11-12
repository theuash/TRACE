"""Block 1: fetch latest 10-K from SEC EDGAR + load ground truth from XBRL Company Facts.
Everything is cached in ./cache so you never hit the SEC twice for the same thing.

Setup:  pip install requests
Run:    python edgar_core.py
"""
import json
import os
import time
from datetime import date

import requests

# SEC rejects requests without a real-looking identity. CHANGE THIS.
USER_AGENT = os.environ.get("SEC_UA", "StudentProject yourname@example.com")
HEADERS = {"User-Agent": USER_AGENT}
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE, exist_ok=True)

# Ground-truth tags per metric, tried in order. kind: "duration" (flow) or "instant" (balance sheet).
METRICS = {
    "revenue": ("duration", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]),
    "net_income": ("duration", ["NetIncomeLoss", "ProfitLoss"]),
    "total_assets": ("instant", ["Assets"]),
    "total_liabilities": ("instant", ["Liabilities"]),
    "operating_cash_flow": ("duration", ["NetCashProvidedByUsedInOperatingActivities"]),
}


def _get(url, cache_name, as_json=True):
    """GET with disk cache + polite rate limiting (SEC limit is 10 req/s)."""
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        return json.loads(data) if as_json else data
    time.sleep(0.2)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    with open(path, "w", encoding="utf-8") as f:
        f.write(r.text)
    return r.json() if as_json else r.text


def ticker_to_cik(ticker):
    data = _get("https://www.sec.gov/files/company_tickers.json", "tickers.json")
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"])
    raise ValueError(f"Unknown ticker {ticker}")


def latest_10k(ticker):
    """Returns dict with cik, accession (dashed), report_date, filing URL, and local html path."""
    cik = ticker_to_cik(ticker)
    sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", f"sub_{cik}.json")
    recent = sub["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            acc = recent["accessionNumber"][i]
            doc = recent["primaryDocument"][i]
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
            html = _get(url, f"{ticker.upper()}_{acc}.htm", as_json=False)
            return {
                "ticker": ticker.upper(), "cik": cik, "accession": acc,
                "report_date": recent["reportDate"][i], "url": url,
                "html_path": os.path.join(CACHE, f"{ticker.upper()}_{acc}.htm"), "html_len": len(html),
            }
    raise ValueError(f"No 10-K found for {ticker}")


def _days(start, end):
    y1, m1, d1 = map(int, start.split("-"))
    y2, m2, d2 = map(int, end.split("-"))
    return (date(y2, m2, d2) - date(y1, m1, d1)).days


def ground_truth(filing):
    """Company Facts values for THIS filing. Matches on accession number first (most reliable)."""
    cf = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{filing['cik']:010d}.json",
              f"facts_{filing['cik']}.json")
    gaap = cf.get("facts", {}).get("us-gaap", {})
    out = {}
    for metric, (kind, tags) in METRICS.items():
        out[metric] = None
        for tag in tags:
            units = gaap.get(tag, {}).get("units", {}).get("USD", [])
            cands = [u for u in units if u.get("accn") == filing["accession"] and u.get("form") == "10-K"
                     and u.get("end") == filing["report_date"]]
            if kind == "duration":  # keep the full-year value, not a quarter
                cands = [u for u in cands if "start" in u and 350 <= _days(u["start"], u["end"]) <= 380]
            if cands:
                out[metric] = {"value": cands[-1]["val"], "tag": tag}
                break
    return out


if __name__ == "__main__":
    for t in ["AAPL", "MSFT", "WMT"]:
        f = latest_10k(t)
        print(t, f["report_date"], f["accession"], f"html chars={f['html_len']}")
        for m, v in ground_truth(f).items():
            print("   ", m, v)
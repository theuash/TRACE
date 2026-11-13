"""Metric -> US-GAAP concept names, most specific first.

XBRL is the answer key, so this file is allowed to know concept names. Extraction must never
import it. A missing tag is a normal outcome: `verify_company` records `truth_value=None` and the
metric shows up in `AccuracyReport.missing_truth` instead of being scored as wrong.
"""

from __future__ import annotations

from shared.schemas import Metric

# Order matters only for reporting which tag was used; the first tag that has a fact for the
# requested period wins. Revenue needs the longest list because filers disagree on the concept.
TAG_MAP: dict[Metric, tuple[str, ...]] = {
    Metric.REVENUE: (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ),
    Metric.NET_INCOME: (
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLoss",
    ),
    Metric.TOTAL_ASSETS: ("Assets",),
    Metric.TOTAL_LIABILITIES: (
        "Liabilities",
        "LiabilitiesCurrent",  # last resort only; rarely the total
    ),
    Metric.SHAREHOLDERS_EQUITY: (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "PartnersCapital",
    ),
    Metric.OPERATING_CASH_FLOW: (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    Metric.OPERATING_INCOME: (
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ),
    Metric.CASH_AND_EQUIVALENTS: (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    Metric.GROSS_PROFIT: ("GrossProfit",),
    Metric.DILUTED_EPS: ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"),
}

# Per-share concepts report under USD/shares, everything else under USD.
UNIT_BY_METRIC: dict[Metric, str] = {Metric.DILUTED_EPS: "USD/shares"}


def tags_for(metric: Metric) -> tuple[str, ...]:
    return TAG_MAP.get(metric, ())


def unit_for(metric: Metric) -> str:
    return UNIT_BY_METRIC.get(metric, "USD")

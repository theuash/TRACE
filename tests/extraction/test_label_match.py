from decimal import Decimal

from extraction.table_parser import match_label, normalise, to_decimal
from shared.schemas import Metric


def test_exact_alias_scores_one():
    assert match_label("Total assets") == (Metric.TOTAL_ASSETS, 1.0)


def test_curly_apostrophe_and_footnote_are_normalised():
    assert normalise("Total Shareholders\u2019 Equity (1):") == "total shareholders' equity"
    assert match_label("Total shareholders\u2019 equity") == (Metric.SHAREHOLDERS_EQUITY, 1.0)


def test_suffix_guess_scores_lower():
    metric, score = match_label("Total Assets, net")
    assert metric is Metric.TOTAL_ASSETS
    assert score < 1.0


def test_unknown_label_returns_none():
    assert match_label("Commitments and contingencies") is None


def test_parentheses_are_negative():
    assert to_decimal("(1,234)") == (Decimal("-1234"), 0.6)


def test_dash_is_zero_with_a_penalty():
    assert to_decimal("\u2014") == (Decimal(0), 0.4)


def test_currency_and_commas_are_clean():
    assert to_decimal("$ 404,548") == (Decimal("404548"), 1.0)


def test_ranges_are_rejected():
    assert to_decimal("100 - 200")[0] is None

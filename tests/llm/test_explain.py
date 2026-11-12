from datetime import date

import pytest

from llm import explain
from shared.schemas import CheckName, ExtractedMetric, Severity, ValidationResult


@pytest.fixture(autouse=True)
def fresh_model_state():
    explain.reset_unavailable()
    explain._explain_cached.cache_clear()
    yield
    explain.reset_unavailable()


def validation(check=CheckName.ACCOUNTING_EQUATION) -> ValidationResult:
    return ValidationResult(
        ticker="AAPL",
        fiscal_year=2026,
        check=check,
        passed=False,
        severity=Severity.ERROR,
        detail="Assets (404,548) != Liabilities (292,455) + Equity (112,093); off by 0.0%",
    )


def boom(*args, **kwargs):
    raise ConnectionError("no model here")


def test_unreachable_model_returns_a_deterministic_sentence(monkeypatch):
    explain._explain_cached.cache_clear()
    monkeypatch.setattr(explain, "complete_text", boom)

    text = explain.explain_anomaly(validation(), None)
    assert "accounting equation" in text.lower()
    assert text == explain.explain_anomaly(validation(), None)


def test_model_answer_is_used_and_tidied(monkeypatch):
    explain._explain_cached.cache_clear()
    monkeypatch.setattr(
        explain, "complete_text", lambda *a, **k: "Assets and liabilities differ. Check row 12."
    )
    text = explain.explain_anomaly(validation(CheckName.YOY_CHANGE), None)
    assert text == "Assets and liabilities differ. Check row 12."


def test_passed_check_needs_no_explanation(monkeypatch):
    explain._explain_cached.cache_clear()
    monkeypatch.setattr(explain, "complete_text", boom)
    passed = validation().model_copy(update={"passed": True})
    assert explain.explain_anomaly(passed, None) == ""


def test_metric_context_is_in_the_fallback(monkeypatch):
    explain._explain_cached.cache_clear()
    monkeypatch.setattr(explain, "complete_text", boom)
    metric = ExtractedMetric(
        ticker="AAPL",
        metric="total_assets",
        fiscal_year=2026,
        period_end=date(2026, 9, 27),
        value=404548000000,
        raw_text="404,548",
        extractor="table",
        confidence=0.9,
        evidence={
            "snippet": "Total assets | 404,548",
            "matched_text": "404,548",
            "location": "balance sheet, row 'Total assets'",
        },
    )
    text = explain.explain_anomaly(validation(), metric)
    assert "404,548" in text

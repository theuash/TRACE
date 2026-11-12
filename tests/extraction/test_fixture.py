from pathlib import Path

import pytest

from shared.schemas import CORE_METRICS, ExtractionResult

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize("ticker", ["aapl", "msft", "tsla", "nvda", "amzn"])
def test_company_fixture_is_a_valid_extraction(ticker):
    path = FIXTURES / f"{ticker}_extraction.json"
    if not path.exists():
        pytest.skip(f"{path.name} missing; run: python -m extraction --fixture {ticker.upper()}")

    result = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
    found = {metric.metric for metric in result.metrics}

    assert result.filing.company.ticker == ticker.upper()
    assert set(CORE_METRICS) <= found
    assert result.prior_metrics, "prior year is required for the YoY check"
    assert all(0.0 <= metric.confidence <= 1.0 for metric in result.metrics)
    assert all(metric.evidence.matched_text in metric.evidence.snippet for metric in result.metrics)

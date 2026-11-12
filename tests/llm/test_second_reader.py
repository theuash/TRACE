import pytest

from llm import second_reader
from shared.schemas import Metric


@pytest.fixture(autouse=True)
def fresh_model_state():
    second_reader.reset_unavailable()
    yield
    second_reader.reset_unavailable()


def test_keeps_only_known_and_numeric_metrics(monkeypatch):
    monkeypatch.setattr(
        second_reader,
        "complete_json",
        lambda *a, **k: {
            "total_assets": "120,500",
            "revenue": "not a number",
            "made_up": "1",
            "net_income": "3,000",
        },
    )
    found = second_reader.read_metrics(
        "Total assets | 120,500", [Metric.TOTAL_ASSETS, Metric.REVENUE, Metric.NET_INCOME]
    )
    assert found == {Metric.TOTAL_ASSETS: "120,500", Metric.NET_INCOME: "3,000"}


def test_unreachable_model_returns_empty(monkeypatch):
    def boom(*args, **kwargs):
        raise TimeoutError("no model")

    monkeypatch.setattr(second_reader, "complete_json", boom)
    assert second_reader.read_metrics("Total assets | 1", [Metric.TOTAL_ASSETS]) == {}


def test_empty_snippet_makes_no_call(monkeypatch):
    monkeypatch.setattr(second_reader, "complete_json", lambda *a, **k: 1 / 0)
    assert second_reader.read_metrics("   ", [Metric.TOTAL_ASSETS]) == {}

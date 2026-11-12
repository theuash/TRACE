import pytest

from llm import second_reader
from shared.schemas import Metric

SNIPPET = (
    "## income statement\nAggregate customer receipts | 478,834 | 391,035\nNet income | 132,175\n"
)


@pytest.fixture(autouse=True)
def fresh():
    second_reader.reset_unavailable()
    yield
    second_reader.reset_unavailable()


def test_label_that_appears_in_the_snippet_is_accepted(monkeypatch):
    monkeypatch.setattr(
        second_reader, "complete_json", lambda *a, **k: {"revenue": "Aggregate customer receipts"}
    )
    assert second_reader.read_labels(SNIPPET, [Metric.REVENUE]) == {
        Metric.REVENUE: "Aggregate customer receipts"
    }


def test_a_label_not_in_the_snippet_is_rejected(monkeypatch):
    monkeypatch.setattr(
        second_reader, "complete_json", lambda *a, **k: {"revenue": "Total revenue we invented"}
    )
    assert second_reader.read_labels(SNIPPET, [Metric.REVENUE]) == {}


def test_a_number_is_never_accepted_as_a_label(monkeypatch):
    monkeypatch.setattr(second_reader, "complete_json", lambda *a, **k: {"revenue": "478,834"})
    assert second_reader.read_labels(SNIPPET, [Metric.REVENUE]) == {}

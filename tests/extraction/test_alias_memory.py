"""A label the LLM read once must be readable by plain Python afterwards."""

from extraction import alias_memory, table_parser
from shared.schemas import Metric

NEW_LABEL = "Consolidated turnover from customers"


def test_unknown_label_is_not_matched_until_it_is_learned():
    assert table_parser.match_label(NEW_LABEL) is None

    alias_memory.learn(table_parser.normalise(NEW_LABEL), Metric.REVENUE)

    assert table_parser.match_label(NEW_LABEL) == (Metric.REVENUE, 0.95)
    assert alias_memory.lookup(table_parser.normalise(NEW_LABEL)) is Metric.REVENUE


def test_a_hand_written_alias_still_beats_a_learned_one():
    label = table_parser.normalise("Total net sales")
    alias_memory.learn(label, Metric.GROSS_PROFIT)  # deliberately wrong

    assert table_parser.match_label("Total net sales") == (Metric.REVENUE, 1.0)


def test_learning_the_same_label_twice_counts_hits():
    label = table_parser.normalise(NEW_LABEL)
    alias_memory.learn(label, Metric.REVENUE)
    alias_memory.learn(label, Metric.REVENUE)

    assert alias_memory.known() == {label: Metric.REVENUE.value}

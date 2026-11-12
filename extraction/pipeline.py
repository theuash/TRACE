"""fetch_filing and extract_filing: the only two functions Person 2 calls from this folder."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO
from typing import Any

import pandas as pd
from lxml import html as lxml_html

from extraction import alias_memory, edgar, locate, segments, table_parser
from extraction.confidence import score_extraction
from extraction.locate import LocatedTable
from extraction.table_parser import SCALE_EXEMPT, STATEMENT_FOR, normalise, to_decimal
from llm import second_reader
from shared.config import get_settings
from shared.schemas import (
    CORE_METRICS,
    OPTIONAL_METRICS,
    Company,
    ExtractedMetric,
    ExtractionResult,
    Extractor,
    FilingRef,
    Metric,
    SourceEvidence,
)

LLM_SECOND_READER = True  # flip to False for a fully offline extraction run
ALL_METRICS: tuple[Metric, ...] = CORE_METRICS + OPTIONAL_METRICS
LLM_ONLY_SCORE = 0.7


def fetch_filing(company: Company) -> FilingRef:
    return edgar.filing_ref(company)


def _index(metrics: list[ExtractedMetric]) -> dict[Metric, ExtractedMetric]:
    return {metric.metric: metric for metric in metrics}


def _scale_for(metric: Metric, located: dict[str, LocatedTable]) -> int:
    if metric in SCALE_EXEMPT:
        return 1
    table = located.get(STATEMENT_FOR.get(metric, ""))
    return table.scale if table is not None else locate.DEFAULT_SCALE


def _derive_total_liabilities(
    metrics: list[ExtractedMetric], located: dict[str, LocatedTable]
) -> ExtractedMetric | None:
    """Amazon has no 'Total liabilities' row: assets - equity, clearly marked as derived."""
    index = _index(metrics)
    if Metric.TOTAL_LIABILITIES in index:
        return None
    assets, equity = index.get(Metric.TOTAL_ASSETS), index.get(Metric.SHAREHOLDERS_EQUITY)
    if assets is None or equity is None:
        return None
    return ExtractedMetric(
        ticker=assets.ticker,
        metric=Metric.TOTAL_LIABILITIES,
        fiscal_year=assets.fiscal_year,
        period_end=assets.period_end,
        value=assets.value - equity.value,
        scale=assets.scale,
        raw_text=f"derived: {assets.raw_text} - {equity.raw_text}",
        extractor=Extractor.DERIVED,
        confidence=0.0,
        confidence_signals={
            "label_match": 0.7,
            "table_type": 1.0,
            "unit_clarity": assets.confidence_signals.get("unit_clarity", 0.5),
            "period_clarity": assets.confidence_signals.get("period_clarity", 0.5),
            "numeric_wellformed": 0.7,
            "extractor_agreement": 0.5,
        },
        evidence=SourceEvidence(
            snippet=assets.evidence.snippet,
            matched_text=assets.evidence.matched_text,
            location=f"{assets.evidence.location} minus equity '{equity.evidence.row_label}'",
            table_index=assets.evidence.table_index,
            row_label="derived total liabilities",
            source_url=assets.evidence.source_url,
        ),
    )


def _table_for(metric: ExtractedMetric, located: dict[str, LocatedTable]) -> LocatedTable | None:
    wanted = metric.evidence.table_index
    for table in located.values():
        if table.table_index == wanted:
            return table
    return None


def _pandas_agreement(
    metric: ExtractedMetric, located: dict[str, LocatedTable], frames: dict[int, Any]
) -> float:
    """Tie-break reader when no model answers: same cell 1.0, different 0.3, unreadable 0.5."""
    table = _table_for(metric, located)
    if table is None:
        return 0.5
    if table.table_index not in frames:
        try:
            markup = lxml_html.tostring(table.node, encoding="unicode")
            parsed = pd.read_html(StringIO(markup))
            frames[table.table_index] = parsed[0] if parsed else None
        except Exception:
            frames[table.table_index] = None
    frame = frames[table.table_index]
    if frame is None or frame.empty:
        return 0.5
    label = normalise(metric.evidence.row_label or "")
    for _, row in frame.iterrows():
        if normalise(str(row.iloc[0])) != label:
            continue
        for cell in row.iloc[1:]:
            value, _ = to_decimal(str(cell))
            if value is not None and value * _scale_for(metric.metric, located) == metric.value:
                return 1.0
        return 0.3
    return 0.5


def _agreement(metric: ExtractedMetric, printed: str, located: dict[str, LocatedTable]) -> float:
    value, _ = to_decimal(printed)
    if value is None:
        return 0.5
    return 1.0 if value * _scale_for(metric.metric, located) == metric.value else 0.3


def _llm_only_metric(
    filing: FilingRef, metric: Metric, printed: str, located: dict[str, LocatedTable], snippet: str
) -> ExtractedMetric:
    value, wellformed = to_decimal(printed)
    scale = _scale_for(metric, located)
    table = located.get(STATEMENT_FOR.get(metric, ""))
    line = next((ln for ln in snippet.splitlines() if printed in ln), printed)
    return ExtractedMetric(
        ticker=filing.company.ticker,
        metric=metric,
        fiscal_year=filing.fiscal_year,
        period_end=(table.current_period_end if table else None) or filing.period_end,
        value=(value or Decimal(0)) * scale,
        scale=scale,
        raw_text=printed,
        extractor=Extractor.LLM,
        confidence=0.0,
        confidence_signals={
            "label_match": 0.7,
            "table_type": 1.0 if table is not None else 0.6,
            "unit_clarity": 1.0 if (table and table.scale_clear) else 0.3,
            "period_clarity": 1.0 if table and table.periods else 0.4,
            "numeric_wellformed": wellformed,
            "extractor_agreement": 0.4,
        },
        evidence=SourceEvidence(
            snippet=line,
            matched_text=printed,
            location=f"read by the LLM from {table.name if table else 'the filing'}",
            table_index=table.table_index if table else None,
            row_label=line.split(" | ")[0],
            source_url=filing.url,
        ),
    )


def _apply_second_opinion(
    filing: FilingRef,
    metrics: list[ExtractedMetric],
    located: dict[str, LocatedTable],
) -> list[ExtractedMetric]:
    """Add the agreement signal, and any metric that only the model found, at low confidence."""
    snippet = second_reader.table_snippet(located) if LLM_SECOND_READER else ""
    wanted = [metric for metric in ALL_METRICS if metric not in _index(metrics)]
    labels = second_reader.read_labels(snippet, wanted) if snippet else {}
    printed_for = {m: _printed_at(label, located) for m, label in labels.items()}
    printed_for = {m: v for m, v in printed_for.items() if v is not None}
    frames: dict[int, Any] = {}

    for metric in metrics:
        printed = printed_for.get(metric.metric)
        score = (
            _agreement(metric, printed, located)
            if printed is not None
            else _pandas_agreement(metric, located, frames)
        )
        metric.confidence_signals["extractor_agreement"] = score

    added: list[ExtractedMetric] = []
    for metric in wanted:
        if metric not in printed_for:
            continue
        read = _llm_only_metric(filing, metric, printed_for[metric], located, snippet)
        added.append(read)
        _learn_alias(read, metric, snippet)
    return metrics + added


def _printed_at(label: str, located: dict[str, LocatedTable]) -> str | None:
    """The printed cell for a row the model named. The number always comes from the parser."""
    wanted = normalise(label)
    for table in located.values():
        for row in table_parser.parse_rows(table.node):
            if normalise(row.label) == wanted and row.raws:
                return row.raws[0]
    return None


def _learn_alias(metric: ExtractedMetric, which: Metric, snippet: str) -> None:
    """Remember a label the model resolved, so the next filing needs no model for it.

    Only unambiguous evidence is learned: the row label must appear exactly once in the snippet
    the model was given, and must not already mean a different metric.
    """
    label = metric.evidence.row_label or ""
    if not label or table_parser.match_label(label) is not None:
        return  # already known, or it disagrees with an existing alias: do not learn
    if snippet.count(label) != 1:
        return  # ambiguous row: which line did the model mean?
    alias_memory.learn(normalise(label), which)


def extract_filing(filing: FilingRef) -> ExtractionResult:
    if not filing.local_path:
        raise FileNotFoundError(f"{filing.company.ticker}: no cached filing on disk")
    settings = get_settings()
    settings.ensure_dirs()
    doc = locate.parse_html(filing.local_path)
    located, warnings = locate.find_statements(doc)

    metrics, prior = table_parser.build_metrics(filing, located)
    derived = _derive_total_liabilities(metrics, located)
    if derived is not None:
        metrics.append(derived)
        warnings.append(
            "Total liabilities is not printed in this filing; derived as assets - equity."
        )
    metrics = _apply_second_opinion(filing, metrics, located)

    missing = [metric.value for metric in ALL_METRICS if metric not in _index(metrics)]
    if missing:
        warnings.append("Metrics not found in the filing: " + ", ".join(missing))

    revenue = _index(metrics).get(Metric.REVENUE)
    segment_tables = segments.find_segments(
        doc, filing, {table.table_index for table in located.values()}, revenue
    )
    result = ExtractionResult(
        filing=filing,
        metrics=metrics,
        prior_metrics=prior,
        segments=segment_tables,
        warnings=warnings,
    )
    return score_extraction(result)

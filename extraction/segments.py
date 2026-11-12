"""Revenue-by-segment table, when the filing has one. Feeds Person 2's segment-sum check."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from extraction.locate import DEFAULT_SCALE, scale_of
from extraction.table_parser import normalise, parse_rows
from shared.schemas import (
    ExtractedMetric,
    FilingRef,
    Metric,
    SegmentTable,
    SegmentValue,
    SourceEvidence,
)

HINTS = ("segment", "geograph", "by region", "by country")


def _is_subtotal(label: str) -> bool:
    return normalise(label).startswith(("total", "subtotal"))


def _nearby_text(table: Any) -> str:
    """Table text plus its nearest heading. Cheap: no document-wide xpath."""
    parts = [" ".join(table.text_content().split())]
    previous = table.getprevious()
    for _ in range(2):
        if previous is None:
            break
        parts.append(" ".join(previous.text_content().split()))
        previous = previous.getprevious()
    return " ".join(parts).lower()


def find_segments(
    doc: Any,
    filing: FilingRef,
    skip_table_indexes: set[int],
    revenue: ExtractedMetric | None,
) -> list[SegmentTable]:
    """One SegmentTable for the current year, or [] when the filing has no segment breakdown."""
    for index, table in enumerate(doc.xpath("//table")):
        if index in skip_table_indexes:
            continue
        nearby = _nearby_text(table)
        if not any(hint in nearby for hint in HINTS):
            continue
        rows = parse_rows(table)
        rows = [row for row in rows if not re.fullmatch(r"[\d\s,.()$%]+", row.label)]
        total = next(
            (
                row
                for row in rows
                if normalise(row.label) in ("total net sales", "total revenues", "total revenue")
            ),
            None,
        )
        if total is None or len(rows) < 3:
            continue
        segments = [
            SegmentValue(name=row.label, value=row.values[0])
            for row in rows
            if row is not total and not _is_subtotal(row.label)
        ]
        if len(segments) < 2:
            continue
        match = scale_of(nearby)
        scale = match or (revenue.scale if revenue else DEFAULT_SCALE)
        return [
            SegmentTable(
                ticker=filing.company.ticker,
                fiscal_year=filing.fiscal_year,
                total_metric=Metric.REVENUE,
                segments=[SegmentValue(name=s.name, value=s.value * scale) for s in segments],
                reported_total=Decimal(total.values[0]) * scale,
                evidence=SourceEvidence(
                    snippet=" | ".join([total.label, *total.raws]),
                    matched_text=total.raws[0],
                    location=f"segment note, row '{total.label}'",
                    table_index=index,
                    row_label=total.label,
                    source_url=filing.url,
                ),
            )
        ]
    return []

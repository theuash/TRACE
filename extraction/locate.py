"""Find the three financial statements inside a 10-K, plus their scale and period columns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from lxml import html as lxml_html

SCALE_BY_WORD = {"thousands": 1_000, "millions": 1_000_000, "billions": 1_000_000_000}
SCALE_RE = re.compile(r"in\s+(thousands|millions|billions)", re.IGNORECASE)
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}  # fmt: skip
DATE_RE = re.compile(r"([A-Z][a-z]+)\.?\s*(\d{1,2}),?\s*(\d{4})")
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
DEFAULT_SCALE = 1_000_000

# Anchors per statement: the first tuple must all be present, the second adds weight to the score.
ANCHORS: dict[str, tuple[tuple[str, ...], tuple[str, ...], int]] = {
    "balance sheet": (
        ("total assets",),
        ("total liabilities", "total current assets", "cash and cash equivalents", "equity"),
        11,
    ),
    "income statement": (
        ("net income",),
        (
            "revenue",
            "net sales",
            "operating income",
            "gross margin",
            "gross profit",
            "cost of sales",
        ),
        13,
    ),
    "cash flow": (
        ("operating activities", "from operations", "cash flows"),
        ("investing", "financing", "depreciation", "net cash"),
        12,
    ),
}


@dataclass(frozen=True)
class LocatedTable:
    """One financial statement table, with the facts needed to read its cells."""

    name: str
    table_index: int
    node: Any
    scale: int
    scale_clear: bool
    periods: list[date] = field(default_factory=list)

    @property
    def current_period_end(self) -> date | None:
        return self.periods[0] if self.periods else None


def parse_html(path: str | Path) -> Any:
    return lxml_html.parse(str(path)).getroot()


def _text(node: Any) -> str:
    return " ".join(node.text_content().split())


def score_table(text: str, name: str) -> int:
    required, extras, threshold = ANCHORS[name]
    low = text.lower()
    if not any(anchor in low for anchor in required):
        return 0
    return threshold + sum(1 for anchor in extras if anchor in low)


def _winner(tables: list[Any], name: str) -> tuple[int, int] | None:
    """Best scoring table; ties go to the fuller table, then the earlier one (notes come later)."""
    best: tuple[int, int, int] | None = None
    for index, table in enumerate(tables):
        text = _text(table)
        score = score_table(text, name)
        if score and (best is None or (score, len(text)) > (best[1], best[2])):
            best = (index, score, len(text))
    return (best[0], best[1]) if best else None


def scale_of(text: str) -> int | None:
    """Nearest 'In millions/thousands/billions' that is not the share-count qualifier.

    Apple's caption reads "(in millions, except number of shares, which are reflected in
    thousands, ...)". A naive last-match picks thousands and every value lands 1000x low, so
    a 'thousands' mention qualified by 'except' or 'reflected' is skipped.
    """
    for match in reversed(list(SCALE_RE.finditer(text))):
        word = match.group(1).lower()
        if word == "thousands":
            lead = text[max(0, match.start() - 60) : match.start()].lower()
            if "except" in lead or "reflected" in lead:
                continue
        return SCALE_BY_WORD[word]
    return None


def _context(node: Any, limit: int = 400) -> str:
    chunks = node.xpath("preceding::text()")[-limit:]
    return " ".join(" ".join(chunk.split()) for chunk in chunks)


def periods_from_dates(text: str) -> list[date]:
    found: list[date] = []
    for month, day, year in DATE_RE.findall(text):
        number = MONTHS.get(month.lower())
        if number:
            found.append(date(int(year), number, int(day)))
    return found


def periods_from_years(cells: list[str]) -> list[date]:
    years = [int(cell) for cell in cells if YEAR_RE.match(cell)]
    return [date(year, 12, 31) for year in sorted(years, reverse=True)]


def _header_cells(table: Any, rows: int = 6) -> list[str]:
    cells: list[str] = []
    for row in table.xpath(".//tr")[:rows]:
        cells.extend(" ".join(cell.text_content().split()) for cell in row.xpath("./td|./th"))
    return cells


def _periods(table: Any) -> list[date]:
    found = periods_from_dates(" ".join(_header_cells(table)))
    if not found:
        found = periods_from_years(_header_cells(table))
    unique: list[date] = []
    for period in found:
        if period not in unique:
            unique.append(period)
    return unique


def locate_statement(tables: list[Any], name: str) -> LocatedTable | None:
    winner = _winner(tables, name)
    if winner is None:
        return None
    index, _score = winner
    table = tables[index]
    scale = scale_of(_text(table))
    if scale is None:
        scale = scale_of(_context(table))
    return LocatedTable(
        name=name,
        table_index=index,
        node=table,
        scale=scale or DEFAULT_SCALE,
        scale_clear=scale is not None,
        periods=_periods(table),
    )


def find_statements(doc: Any) -> tuple[dict[str, LocatedTable], list[str]]:
    tables = doc.xpath("//table")
    found: dict[str, LocatedTable] = {}
    warnings: list[str] = []
    for name in ANCHORS:
        located = locate_statement(tables, name)
        if located is None:
            warnings.append(f"Could not locate the {name} table in this filing.")
        else:
            found[name] = located
    return found, warnings

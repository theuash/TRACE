"""Optional LLM second extractor. Reads only the located tables, returns printed cell text."""

from __future__ import annotations

from extraction.locate import LocatedTable
from extraction.table_parser import parse_rows, to_decimal
from llm.client import complete_json
from shared.config import get_settings
from shared.schemas import Metric

SYSTEM = (
    "You read rows of US 10-K financial statement tables and copy cell text exactly as printed. "
    "Never compute, never scale, never guess. Reply with JSON only."
)
MAX_SNIPPET_CHARS = 6000
READER_TIMEOUT_S = 5.0
_unavailable = False  # first failure turns the reader off for the rest of the process


def reset_unavailable() -> None:
    global _unavailable
    _unavailable = False


def table_snippet(located: dict[str, LocatedTable]) -> str:
    lines: list[str] = []
    for name, table in located.items():
        lines.append(f"## {name}")
        for row in parse_rows(table.node):
            lines.append(" | ".join([row.label, *row.raws]))
    return "\n".join(lines)[:MAX_SNIPPET_CHARS]


def build_prompt(snippet: str, metrics: list[Metric]) -> str:
    keys = ", ".join(f'"{metric.value}"' for metric in metrics)
    return (
        "From the table rows below, return the printed cell text for each metric you can find.\n"
        f"Use exactly these JSON keys: {keys}. Omit a key you cannot find. Use the FIRST numeric "
        "column (the most recent period).\n\n" + snippet
    )


def read_metrics(
    snippet: str, metrics: list[Metric], model: str | None = None
) -> dict[Metric, str]:
    """{} on any failure: the deterministic parser must never depend on this module."""
    global _unavailable
    if _unavailable or not snippet.strip() or not metrics:
        return {}
    try:
        data = complete_json(
            build_prompt(snippet, metrics),
            system=SYSTEM,
            model=model or get_settings().llm_model_extract,
            max_tokens=400,
            timeout=READER_TIMEOUT_S,
        )
    except Exception:
        _unavailable = True
        return {}
    found: dict[Metric, str] = {}
    for key, value in data.items():
        try:
            metric = Metric(key)
        except ValueError:
            continue
        if metric not in metrics or not isinstance(value, str):
            continue
        if to_decimal(value)[0] is not None:
            found[metric] = value.strip()
    return found

"""Labels the LLM has already matched, remembered so the parser never needs the LLM twice.

The table parser stays the primary reader. This store only holds labels a model has already read
correctly once: the next filing is parsed with plain Python, no model call.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from shared.config import get_settings
from shared.schemas import Metric

LEARNED_LABEL_MATCH = 0.95  # below a hand-written exact alias (1.00), above a regex (0.85)


def _connect() -> sqlite3.Connection:
    path = get_settings().data_dir / "aliases.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE IF NOT EXISTS learned_aliases ("
        " label TEXT PRIMARY KEY, metric TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 1,"
        " learned_at TEXT NOT NULL)"
    )
    return db


def lookup(label: str) -> Metric | None:
    """The metric a previous run learned for this normalised label. Never raises."""
    if not label:
        return None
    try:
        with _connect() as db:
            row = db.execute(
                "SELECT metric FROM learned_aliases WHERE label=?", (label,)
            ).fetchone()
        return Metric(row[0]) if row else None
    except (sqlite3.Error, ValueError):
        return None


def learn(label: str, metric: Metric) -> None:
    """Remember one label the model matched. Never raises: learning must not break extraction."""
    if not label.strip():
        return
    try:
        with _connect() as db:
            db.execute(
                "INSERT INTO learned_aliases (label, metric, hits, learned_at)"
                " VALUES (?,?,1,?) ON CONFLICT(label) DO UPDATE SET hits=hits+1",
                (label, metric.value, datetime.now(UTC).isoformat()),
            )
    except sqlite3.Error:
        pass


def known() -> dict[str, str]:
    """Every learned label, for the UI/debug and for docs. Never raises."""
    try:
        with _connect() as db:
            return dict(db.execute("SELECT label, metric FROM learned_aliases").fetchall())
    except sqlite3.Error:
        return {}

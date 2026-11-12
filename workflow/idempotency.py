"""Idempotency ledger for side effects.

Key: `(run_id, step, item_id)`. Every fetch, extraction and audit write goes through `run_once`,
so a resumed graph that re-runs a node from its first line cannot repeat the effect or the LLM call.
The stored payload lets the node resume with the value it had before the kill.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS side_effects (
    run_id     TEXT NOT NULL,
    step       TEXT NOT NULL,
    item_id    TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, step, item_id)
);
"""


class IdempotencyStore:
    """One SQLite file next to the checkpoints, so a restart sees the same ledger."""

    def __init__(self, path: str | Path = "data/idempotency.db") -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> IdempotencyStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def done(self, run_id: str, step: str, item_id: str = "run") -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM side_effects WHERE run_id=? AND step=? AND item_id=?",
            (run_id, step, item_id),
        ).fetchone()
        return row is not None

    def run_once(
        self,
        run_id: str,
        step: str,
        item_id: str,
        fn: Callable[[], T],
        *,
        model: type[BaseModel] | None = None,
    ) -> T | None:
        """Execute `fn` exactly once per key. On a repeat, replay the stored value instead."""
        row = self._conn.execute(
            "SELECT payload FROM side_effects WHERE run_id=? AND step=? AND item_id=?",
            (run_id, step, item_id),
        ).fetchone()
        if row is not None:
            if model is not None:
                return model.model_validate_json(row[0])
            return json.loads(row[0])
        value = fn()
        if isinstance(value, BaseModel):
            payload = value.model_dump_json()
        else:
            payload = json.dumps(value, default=str)
        self._conn.execute(
            "INSERT INTO side_effects (run_id, step, item_id, payload) VALUES (?, ?, ?, ?)",
            (run_id, step, item_id, payload),
        )
        return value

    def counts(self, run_id: str) -> dict[str, int]:
        """Per-step executions. Single-item steps (fetch, extract) must stay at 1."""
        rows = self._conn.execute(
            "SELECT step, COUNT(*) FROM side_effects WHERE run_id=? GROUP BY step",
            (run_id,),
        ).fetchall()
        return {str(step): int(n) for step, n in rows}


_STORE: IdempotencyStore | None = None


def get_store(path: str | Path | None = None) -> IdempotencyStore:
    global _STORE
    if path is not None:
        return IdempotencyStore(path)
    if _STORE is None:
        from shared.config import get_settings

        settings = get_settings()
        _STORE = IdempotencyStore(settings.data_dir / "idempotency.db")
    return _STORE

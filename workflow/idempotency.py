"""Idempotency ledger for side effects, stored in PostgreSQL (Neon).

Key: `(run_id, step, item_id)`. Every fetch, extraction and audit write goes through `run_once`,
so a resumed graph that re-runs a node from its first line cannot repeat the effect or the LLM call.
The stored payload lets the node resume with the value it had before the kill.

The ledger lives next to the runs and the checkpoints, so a restart sees the same rows.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from db.postgres import Database, get_database

T = TypeVar("T")


class IdempotencyStore:
    """The `side_effects` table, in PostgreSQL."""

    def __init__(self, dsn: str | None = None, *, schema: str = "public") -> None:
        self._db = Database(dsn, schema=schema) if dsn else get_database()

    # ------------------------------------------------------------------ lifecycle
    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> IdempotencyStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ ledger
    def done(self, run_id: str, step: str, item_id: str = "run") -> bool:
        row = self._db.fetch_one(
            "SELECT 1 FROM side_effects WHERE run_id=%s AND step=%s AND item_id=%s",
            (run_id, step, item_id),
        )
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
        row = self._db.fetch_one(
            "SELECT payload FROM side_effects WHERE run_id=%s AND step=%s AND item_id=%s",
            (run_id, step, item_id),
        )
        if row is not None:
            payload = str(row["payload"])
            if model is not None:
                return model.model_validate_json(payload)
            return json.loads(payload)
        value = fn()
        if isinstance(value, BaseModel):
            payload = value.model_dump_json()
        else:
            payload = json.dumps(value, default=str)
        # ON CONFLICT DO NOTHING: if a parallel writer won the race, its payload is the truth.
        self._db.execute(
            "INSERT INTO side_effects (run_id, step, item_id, payload) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (run_id, step, item_id) DO NOTHING",
            (run_id, step, item_id, payload),
        )
        return value

    def counts(self, run_id: str) -> dict[str, int]:
        """Per-step executions. Single-item steps (fetch, extract) must stay at 1."""
        rows = self._db.fetch_all(
            "SELECT step, count(*) AS n FROM side_effects WHERE run_id=%s GROUP BY step",
            (run_id,),
        )
        return {str(row["step"]): int(row["n"]) for row in rows}


_STORE: IdempotencyStore | None = None


def get_store(dsn: str | None = None, *, schema: str = "public") -> IdempotencyStore:
    global _STORE
    if dsn is not None:
        return IdempotencyStore(dsn, schema=schema)
    if _STORE is None:
        _STORE = IdempotencyStore()
    return _STORE


def reset_store_singleton() -> None:
    """Tests switch databases; this drops the cached process-wide store."""
    global _STORE
    _STORE = None

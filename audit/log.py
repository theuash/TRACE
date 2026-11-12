"""Append-only, hash-chained audit log.

Two independent layers stop history being rewritten:

1. SQLite triggers `RAISE(ABORT)` on any UPDATE or DELETE of `audit_entries`.
2. Every row stores `prev_hash` and `hash = AuditEntry.compute_hash()`, so even a direct file edit
   is detectable by `audit/verify.py`.

`append()` is the only writer. There is deliberately no update and no delete method.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shared.schemas import GENESIS_HASH, AuditAction, AuditEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_entries (
    seq     INTEGER PRIMARY KEY,
    payload TEXT NOT NULL,
    hash    TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_entries_no_update
BEFORE UPDATE ON audit_entries
BEGIN
    SELECT RAISE(ABORT, 'audit log is append-only: UPDATE is forbidden');
END;
CREATE TRIGGER IF NOT EXISTS audit_entries_no_delete
BEFORE DELETE ON audit_entries
BEGIN
    SELECT RAISE(ABORT, 'audit log is append-only: DELETE is forbidden');
END;
"""


class AuditLog:
    """One SQLite file, one table, write-once rows."""

    def __init__(self, path: str | Path = "data/audit.db") -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> AuditLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _last(self) -> tuple[int, str]:
        row = self._conn.execute(
            "SELECT seq, hash FROM audit_entries ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return (0, GENESIS_HASH) if row is None else (int(row[0]), str(row[1]))

    def append(self, *, actor: str, action: AuditAction, **fields: object) -> AuditEntry:
        """The only writer: seals the row and links it to its predecessor."""
        seq, prev_hash = self._last()
        entry = AuditEntry(
            seq=seq + 1, actor=actor, action=action, prev_hash=prev_hash, **fields
        ).seal()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT INTO audit_entries (seq, payload, hash) VALUES (?, ?, ?)",
                (entry.seq, entry.canonical_payload(), entry.hash),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return entry

    def entries(self) -> list[AuditEntry]:
        rows = self._conn.execute("SELECT payload, hash FROM audit_entries ORDER BY seq").fetchall()
        out: list[AuditEntry] = []
        for payload, stored_hash in rows:
            entry = AuditEntry.model_validate_json(payload)
            out.append(entry.model_copy(update={"hash": stored_hash}))
        return out

    def raw_entries(self) -> list[tuple[int, str, str]]:
        """(seq, payload, hash) exactly as stored, for the verifier."""
        return [
            (int(seq), str(payload), str(stored))
            for seq, payload, stored in self._conn.execute(
                "SELECT seq, payload, hash FROM audit_entries ORDER BY seq"
            )
        ]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM audit_entries").fetchone()
        return int(row[0])


_DEFAULT: AuditLog | None = None


def get_log(path: str | Path | None = None) -> AuditLog:
    """Process-wide log, so the workflow service and the API see the same rows."""
    global _DEFAULT
    if path is not None:
        return AuditLog(path)
    if _DEFAULT is None:
        from shared.config import get_settings

        _DEFAULT = AuditLog(get_settings().audit_db_path)
    return _DEFAULT

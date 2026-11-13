"""Append-only, hash-chained audit log, stored in PostgreSQL (Neon).

Two independent layers stop history being rewritten:

1. Database triggers raise on any UPDATE, DELETE or TRUNCATE of `audit_entries`
   (see `db/migrations/0003_append_only.sql` and `0004_append_only_truncate.sql`).
2. Every row stores `prev_hash` and `hash = AuditEntry.compute_hash()`, so even a change that
   bypassed the database is detectable by `audit/verify.py`.

`append()` is the only writer. There is deliberately no update and no delete method.
"""

from __future__ import annotations

import sys
from typing import Any

from db.postgres import Database, get_database
from shared.config import get_settings
from shared.schemas import GENESIS_HASH, AuditAction, AuditEntry

# Serialises appends across processes: the chain needs a strict order of seq numbers, and two
# workers must never pick the same one.
_APPEND_LOCK_KEY = 913_245_771


def _under_test() -> bool:
    return "pytest" in sys.modules


class AuditLog:
    """One table, write-once rows, in PostgreSQL."""

    def __init__(self, dsn: str | None = None, *, schema: str = "public") -> None:
        self._db = Database(dsn, schema=schema) if dsn else get_database()

    # ------------------------------------------------------------------ lifecycle
    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> AuditLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ writing
    def _last(self) -> tuple[int, str]:
        row = self._db.fetch_one("SELECT seq, hash FROM audit_entries ORDER BY seq DESC LIMIT 1")
        return (0, GENESIS_HASH) if row is None else (int(row["seq"]), str(row["hash"]))

    def append(self, *, actor: str, action: AuditAction, **fields: object) -> AuditEntry:
        """The only writer: seals the row and links it to its predecessor."""
        if _under_test() and self._db.schema == get_settings().db_schema:
            raise RuntimeError(
                "refusing to append to the application schema from a test: use the db_context "
                "fixture (or pass schema=...) so the demo chain is never touched"
            )
        with self._db.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (_APPEND_LOCK_KEY,))
                    cur.execute("SELECT seq, hash FROM audit_entries ORDER BY seq DESC LIMIT 1")
                    row = cur.fetchone()
                    seq, prev_hash = (
                        (0, GENESIS_HASH)
                        if row is None
                        else (
                            int(row["seq"]),
                            str(row["hash"]),
                        )
                    )
                    entry = AuditEntry(
                        seq=seq + 1, actor=actor, action=action, prev_hash=prev_hash, **fields
                    ).seal()
                    cur.execute(
                        "INSERT INTO audit_entries (seq, payload, hash) VALUES (%s, %s, %s)",
                        (entry.seq, entry.canonical_payload(), entry.hash),
                    )
            conn.commit()
        return entry

    # ------------------------------------------------------------------ reading
    def entries(self) -> list[AuditEntry]:
        out: list[AuditEntry] = []
        for row in self._db.fetch_all("SELECT payload, hash FROM audit_entries ORDER BY seq"):
            entry = AuditEntry.model_validate_json(str(row["payload"]))
            out.append(entry.model_copy(update={"hash": str(row["hash"])}))
        return out

    def read_entries(self) -> tuple[list[AuditEntry], list[int]]:
        """Tolerant read: one unparsable row is reported, never fatal.

        The chain is still broken - `verify_log` is what says so - but a single corrupt row must
        not take the whole dashboard down. Callers show the returned seq numbers to the reviewer.
        """
        entries: list[AuditEntry] = []
        corrupt: list[int] = []
        for row in self._db.fetch_all("SELECT seq, payload, hash FROM audit_entries ORDER BY seq"):
            try:
                entry = AuditEntry.model_validate_json(str(row["payload"]))
            except ValueError:
                corrupt.append(int(row["seq"]))
                continue
            entries.append(entry.model_copy(update={"hash": str(row["hash"])}))
        return entries, corrupt

    def raw_entries(self) -> list[tuple[int, str, str]]:
        """(seq, payload, hash) exactly as stored, for the verifier."""
        return [
            (int(row["seq"]), str(row["payload"]), str(row["hash"]))
            for row in self._db.fetch_all(
                "SELECT seq, payload, hash FROM audit_entries ORDER BY seq"
            )
        ]

    def count(self) -> int:
        row = self._db.fetch_one("SELECT count(*) AS n FROM audit_entries")
        return int(row["n"]) if row else 0

    def table_counts(self) -> dict[str, int]:
        return self._db.table_counts(["audit_entries"])


_DEFAULT: AuditLog | None = None


def get_log(dsn: str | None = None) -> AuditLog:
    """Process-wide log, so the workflow service and the API see the same rows."""
    global _DEFAULT
    if dsn is not None:
        return AuditLog(dsn)
    if _DEFAULT is None:
        _DEFAULT = AuditLog()
    return _DEFAULT


def reset_log_singleton() -> None:
    """Tests switch databases; this drops the cached process-wide log."""
    global _DEFAULT
    _DEFAULT = None


def database_of(log: AuditLog) -> Database:
    """The database behind a log, for health checks and row counts."""
    return log._db  # noqa: SLF001 - same package, deliberately simple


def append_fields(entry: AuditEntry) -> dict[str, Any]:
    """The fields of an entry as a plain dict (used by the API layer)."""
    return entry.model_dump(mode="json")

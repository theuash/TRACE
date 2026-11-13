"""PostgreSQL access for TRACE: one pool, one health check, one migration runner.

Neon specifics that shaped this module:

* the **pooled** URL goes through PgBouncer, so many clients share a small number of server
  connections - that is why the pool is small and every query is short;
* a **cold** project (idle branch) wakes up on the first connection and that can take a few
  seconds - `ping()` and the first query therefore retry once instead of failing;
* credentials never leave the process: the URL is only ever printed as a host name.
"""

from __future__ import annotations

import atexit
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from psycopg import Connection, Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from shared.config import Settings, get_settings


class DatabaseUnavailable(RuntimeError):
    """The database could not be reached. The API turns this into a 503, never a hang."""


class Database:
    """A thin, explicit wrapper around a psycopg connection pool."""

    def __init__(
        self,
        url: str,
        *,
        min_size: int = 1,
        max_size: int = 5,
        connect_timeout_s: float = 10.0,
        statement_timeout_ms: int = 15_000,
        schema: str = "public",
    ) -> None:
        self.url = url
        self.schema = schema
        self._statement_timeout_ms = statement_timeout_ms
        # The Neon pooler (PgBouncer, transaction mode) refuses session parameters in the
        # startup packet (`statement_timeout`, `search_path`). So neither is sent at startup:
        # the timeout is set per transaction with SET LOCAL, and the schema is set the same way.
        self._pool = ConnectionPool(
            conninfo=url,
            min_size=min_size,
            max_size=max_size,
            timeout=connect_timeout_s,
            kwargs={
                "connect_timeout": int(connect_timeout_s),
                "row_factory": dict_row,
            },
            open=False,
        )
        self._lock = threading.Lock()
        self._opened = False
        self._last_ping: dict[str, Any] | None = None

    # ------------------------------------------------------------------ lifecycle
    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Database | None:
        settings = settings or get_settings()
        url = settings.database_url
        if not url:
            return None
        return cls(
            url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            connect_timeout_s=settings.db_connect_timeout_s,
            statement_timeout_ms=settings.db_statement_timeout_ms,
            schema=settings.db_schema,
        )

    def open(self) -> None:
        with self._lock:
            if not self._opened:
                self._pool.open()
                self._opened = True

    def close(self) -> None:
        with self._lock:
            if self._opened:
                self._pool.close()
                self._opened = False

    # ------------------------------------------------------------------ queries
    @contextmanager
    def connection(self) -> Iterator[Connection]:
        self.open()
        try:
            with self._pool.connection() as conn:
                # Every statement in this connection sees the same schema and timeout.
                with conn.cursor() as cur:
                    self.apply_session(cur)
                yield conn
        except Exception as exc:  # pragma: no cover - depends on the server
            raise DatabaseUnavailable(str(exc)) from exc

    @contextmanager
    def cursor(self, *, commit: bool = True) -> Iterator[Cursor]:
        """A cursor in its own transaction. `commit=False` rolls back on exit."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                self.apply_session(cur)
                yield cur
            if commit:
                conn.commit()

    def apply_session(self, cur: Cursor) -> None:
        """Transaction-scoped settings: they never leak to the next client of the pool."""
        if self._statement_timeout_ms:
            cur.execute(f"SET LOCAL statement_timeout = {int(self._statement_timeout_ms)}")
        if self.schema != "public":
            cur.execute(f'SET LOCAL search_path = "{self.schema}"')

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall()) if cur.description else []

    def fetch_one(self, sql: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        with self.cursor(commit=False) as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetch_all(self, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        with self.cursor(commit=False) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    # ------------------------------------------------------------------ health
    def ping(self, *, retries: int = 2) -> dict[str, Any]:
        """Round-trip to the server. Retries once: a cold Neon project needs a second try."""
        started = time.perf_counter()
        last_error: str | None = None
        for attempt in range(retries):
            try:
                with self.cursor(commit=False) as cur:
                    cur.execute("SELECT 1 AS ok")
                    cur.fetchone()
                result = {
                    "ok": True,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "attempts": attempt + 1,
                    "error": None,
                }
                self._last_ping = result
                return result
            except Exception as exc:
                message = str(exc).strip()
                last_error = message.splitlines()[0] if message else exc.__class__.__name__
                if attempt + 1 < retries:
                    time.sleep(1.5)
        result = {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "attempts": retries,
            "error": last_error,
        }
        self._last_ping = result
        return result

    @property
    def last_ping(self) -> dict[str, Any] | None:
        """The last round-trip result, so a liveness check never waits for the database."""
        return self._last_ping

    def table_counts(self, tables: Sequence[str]) -> dict[str, int]:
        """Row count per table. Missing tables count as zero."""
        counts: dict[str, int] = {}
        for table in tables:
            row = self.fetch_one(f'SELECT count(*) AS n FROM "{table}"')
            counts[table] = int(row["n"]) if row else 0
        return counts

    def last_write(self, table: str, column: str = "timestamp") -> str | None:
        row = self.fetch_one(f'SELECT max("{column}") AS ts FROM "{table}"')
        return str(row["ts"]) if row and row.get("ts") else None


_DATABASE: Database | None = None
_DATABASE_LOCK = threading.Lock()


def get_database() -> Database:
    """The process-wide database. Raises DatabaseUnavailable when none is configured."""
    global _DATABASE
    with _DATABASE_LOCK:
        if _DATABASE is None:
            db = Database.from_settings()
            if db is None:
                raise DatabaseUnavailable(
                    "No database configured. Set NEON_POOL_URL in .env (and NEON_DIRECT_URL "
                    "for migrations)."
                )
            _DATABASE = db
        return _DATABASE


def reset_database_singleton() -> None:
    """Tests and the settings page use this to pick up a new URL."""
    global _DATABASE
    with _DATABASE_LOCK:
        if _DATABASE is not None:
            _DATABASE.close()
        _DATABASE = None


@atexit.register
def _close_pool_on_exit() -> None:
    """Never leave pool threads behind: the process must exit cleanly."""
    global _DATABASE
    with _DATABASE_LOCK:
        if _DATABASE is not None:
            try:
                _DATABASE.close()
            except Exception:  # pragma: no cover - best effort at exit
                pass
            _DATABASE = None

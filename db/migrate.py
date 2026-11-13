"""Migration runner: applies `db/migrations/*.sql` in order, once.

    uv run python -m db.migrate            # apply everything that is pending
    uv run python -m db.migrate --status   # what is applied, what is pending

Migrations use the direct URL when one is configured (Neon wants a real session for DDL) and
fall back to the pooled URL otherwise. Every file runs inside its own transaction, and the
version is recorded in `schema_migrations`, so re-running is a no-op.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from psycopg import Connection

from db.postgres import Database, DatabaseUnavailable
from shared.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _ensure_registry(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            ")"
        )
    conn.commit()


def applied_versions(conn: Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {str(row["version"]) for row in cur.fetchall()}


def migrate(database: Database) -> list[str]:
    """Apply every pending migration. Returns the versions that were applied."""
    applied: list[str] = []
    with database.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # The schema is transaction-scoped, so the tables land in the right place.
                database.apply_session(cur)
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    " version TEXT PRIMARY KEY,"
                    " applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                    ")"
                )
                cur.execute("SELECT version FROM schema_migrations")
                done = {str(row["version"]) for row in cur.fetchall()}
            for path in _migration_files():
                version = path.stem
                if version in done:
                    continue
                with conn.cursor() as cur:
                    database.apply_session(cur)
                    cur.execute(path.read_text(encoding="utf-8"))
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)"
                        " ON CONFLICT DO NOTHING",
                        (version,),
                    )
                applied.append(version)
    return applied


def status(database: Database) -> tuple[list[str], list[str]]:
    with database.connection() as conn:
        _ensure_registry(conn)
        done = applied_versions(conn)
    files = [path.stem for path in _migration_files()]
    return done, [v for v in files if v not in done]


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply TRACE database migrations.")
    parser.add_argument("--status", action="store_true", help="only show what is applied/pending")
    args = parser.parse_args()

    settings = get_settings()
    url = settings.migration_database_url
    if not url:
        print("No database configured. Set NEON_POOL_URL (and NEON_DIRECT_URL) in .env.")
        return 1

    database = Database(
        url,
        min_size=1,
        max_size=1,
        connect_timeout_s=settings.db_connect_timeout_s,
        statement_timeout_ms=max(settings.db_statement_timeout_ms, 60_000),
        schema=settings.db_schema,
    )
    try:
        if args.status:
            done, pending = status(database)
            print(f"applied:  {', '.join(done) or '-'}")
            print(f"pending:  {', '.join(pending) or '-'}")
            return 0
        applied = migrate(database)
        print(f"applied {len(applied)} migration(s): {', '.join(applied) or '-'}")
        return 0
    except DatabaseUnavailable as exc:
        print(f"database unavailable: {exc}")
        return 2
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())

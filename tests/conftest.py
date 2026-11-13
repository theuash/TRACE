"""Test fixtures.

The database is PostgreSQL now, so the tests get their own **schema** inside it: a unique
schema per test session, the migrations applied there, and the schema dropped at the end.
Nothing a test writes can reach the demo data.

Without a configured database the database tests skip instead of failing.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from shared.config import get_settings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own data dir and fake providers."""
    monkeypatch.setenv("USE_FAKES", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SEC_USER_AGENT", "Test Runner test@example.com")
    get_settings.cache_clear()

    import audit.log as audit_log
    import workflow.idempotency as idem

    audit_log._DEFAULT = None
    idem._STORE = None
    yield tmp_path
    get_settings.cache_clear()
    audit_log._DEFAULT = None
    idem._STORE = None


@dataclass
class TestDatabase:
    dsn: str
    schema: str


@pytest.fixture(scope="session")
def postgres():
    """A throw-away schema in the configured database, with the migrations applied."""
    from db.migrate import migrate
    from db.postgres import Database

    settings = get_settings()
    url = settings.database_url
    if not url:
        pytest.skip("No database configured (NEON_POOL_URL / NEON_DIRECT_URL).")
    schema = f"test_{uuid4().hex[:12]}"
    database = Database(url, schema=schema, min_size=1, max_size=3)
    try:
        database.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        migrate(database)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Database not reachable: {exc}")
    yield TestDatabase(dsn=url, schema=schema)
    try:
        database.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    finally:
        database.close()


@pytest.fixture()
def db_context(postgres):
    """Point the process-wide singletons at the test schema.

    The workflow writes audit rows through `get_log()` and side effects through `get_store()`;
    in a test they must land in the throw-away schema, never in the demo data.
    """
    from audit.log import AuditLog
    from db.postgres import Database
    from workflow.idempotency import IdempotencyStore

    import audit.log as audit_log
    import workflow.idempotency as idem

    # Every test starts from an empty store.
    database = Database(postgres.dsn, schema=postgres.schema)
    with database.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE audit_entries DISABLE TRIGGER audit_entries_no_truncate")
            cur.execute("TRUNCATE runs, side_effects, kv, audit_entries")
            cur.execute("ALTER TABLE audit_entries ENABLE TRIGGER audit_entries_no_truncate")
        conn.commit()
    database.close()

    audit_log._DEFAULT = AuditLog(postgres.dsn, schema=postgres.schema)
    idem._STORE = IdempotencyStore(postgres.dsn, schema=postgres.schema)
    yield postgres
    audit_log._DEFAULT = None
    idem._STORE = None

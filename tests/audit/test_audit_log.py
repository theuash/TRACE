"""The audit log is append-only and hash-chained - in PostgreSQL, with real triggers."""

import json

import psycopg
import pytest

from audit.log import AuditLog
from audit.verify import verify_log
from shared.config import get_settings
from shared.schemas import GENESIS_HASH, AuditAction


def _log(db_context) -> AuditLog:
    return AuditLog(db_context.dsn, schema=db_context.schema)


def test_entries_are_sealed_and_linked(db_context):
    log = _log(db_context)
    for i in range(4):
        log.append(
            actor="tester",
            action=AuditAction.HUMAN_DECISION,
            run_id=f"R{i}",
            metric_id="AAPL:revenue:2024",
            note=f"decision {i}",
        )
    entries = log.entries()
    assert [e.seq for e in entries] == [1, 2, 3, 4]
    assert entries[0].prev_hash == GENESIS_HASH
    for prev, cur in zip(entries, entries[1:], strict=False):
        assert cur.prev_hash == prev.hash
    assert all(e.hash == e.compute_hash() for e in entries)
    assert verify_log(log).ok


def test_update_and_delete_are_refused_by_the_database(db_context):
    log = _log(db_context)
    log.append(actor="tester", action=AuditAction.AUTO_APPROVAL, run_id="R1", metric_id="m")

    def attempt(statement: str) -> None:
        # A fresh connection per statement: a refused statement aborts its transaction.
        with log._db.connection() as conn:  # noqa: SLF001 - the point is to bypass the writer
            with conn.cursor() as cur:
                with pytest.raises(psycopg.Error, match="append-only"):
                    cur.execute(statement)
            conn.rollback()

    attempt("UPDATE audit_entries SET payload='{}' WHERE seq=1")
    attempt("DELETE FROM audit_entries WHERE seq=1")
    attempt("TRUNCATE audit_entries")
    assert verify_log(log).ok


def test_a_tampered_row_is_detected_even_when_the_triggers_are_dropped(db_context):
    log = _log(db_context)
    for i in range(3):
        log.append(actor="tester", action=AuditAction.HUMAN_DECISION, run_id="R", note=str(i))
    assert verify_log(log).ok

    with log._db.connection() as conn:  # noqa: SLF001
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE audit_entries DISABLE TRIGGER audit_entries_no_update")
            cur.execute("UPDATE audit_entries SET payload=%s WHERE seq=2", ('{"seq":2}',))
        conn.commit()

    result = verify_log(log)
    assert result.ok is False
    assert result.first_broken_seq == 2
    assert "not a valid audit entry" in result.message


def test_a_row_with_changed_content_is_detected(db_context):
    log = _log(db_context)
    log.append(actor="tester", action=AuditAction.HUMAN_DECISION, run_id="R", note="real")
    log.append(actor="tester", action=AuditAction.HUMAN_DECISION, run_id="R", note="real")
    entries = log.entries()
    forged = entries[1].model_copy(update={"note": "not what was approved"})
    forged = forged.seal()
    row = json.loads(forged.canonical_payload())
    row["hash"] = forged.hash
    with log._db.connection() as conn:  # noqa: SLF001
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE audit_entries DISABLE TRIGGER audit_entries_no_update")
            cur.execute(
                "UPDATE audit_entries SET payload=%s WHERE seq=2",
                (json.dumps(row, sort_keys=True, separators=(",", ":")),),
            )
        conn.commit()
    result = verify_log(log)
    assert result.ok is False
    assert result.first_broken_seq == 2
    assert "do not match" in result.message


def test_a_test_cannot_write_to_the_application_schema():
    """The demo chain was once corrupted by a test run: now the writer refuses outright."""
    log = AuditLog("postgresql://nobody@127.0.0.1:1/none", schema=get_settings().db_schema)
    with pytest.raises(RuntimeError, match="application schema"):
        log.append(actor="tester", action=AuditAction.AUTO_APPROVAL, run_id="R")


def test_a_corrupt_row_does_not_stop_the_dashboard_reading_decisions(db_context):
    """The status page must still render: the corrupt row is reported, not raised."""
    log = _log(db_context)
    for i in range(3):
        log.append(
            actor="tester",
            action=AuditAction.HUMAN_DECISION,
            run_id="R",
            metric_id=f"AAPL:revenue:202{i}",
            note=str(i),
        )
    with log._db.connection() as conn:  # noqa: SLF001
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE audit_entries DISABLE TRIGGER audit_entries_no_update")
            cur.execute("UPDATE audit_entries SET payload=%s WHERE seq=2", ('{"seq":2}',))
        conn.commit()

    entries, corrupt = log.read_entries()
    assert corrupt == [2]
    assert [e.seq for e in entries] == [1, 3]
    with pytest.raises(Exception, match="actor"):
        log.entries()

import sqlite3

import pytest

from audit.log import AuditLog
from audit.verify import verify_log
from shared.schemas import GENESIS_HASH, AuditAction


def _log(tmp_path) -> AuditLog:
    return AuditLog(tmp_path / "audit.db")


def test_entries_are_sealed_and_linked(tmp_path):
    log = _log(tmp_path)
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


def test_update_and_delete_are_refused_by_the_database(tmp_path):
    log = _log(tmp_path)
    log.append(actor="tester", action=AuditAction.AUTO_APPROVAL, run_id="R1", metric_id="m")
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE audit_entries SET payload='{}' WHERE seq=1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM audit_entries WHERE seq=1")
    assert verify_log(log).ok


def test_a_tampered_row_is_detected_even_when_the_triggers_are_dropped(tmp_path):
    log = _log(tmp_path)
    for i in range(3):
        log.append(actor="tester", action=AuditAction.HUMAN_DECISION, run_id="R", note=str(i))
    assert verify_log(log).ok

    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    conn.execute("DROP TRIGGER audit_entries_no_update")
    conn.execute("UPDATE audit_entries SET payload=? WHERE seq=2", ('{"seq":2}',))
    conn.commit()

    result = verify_log(log)
    assert result.ok is False
    assert result.first_broken_seq == 2
    assert "not a valid audit entry" in result.message


def test_a_row_with_changed_content_is_detected(tmp_path):
    log = _log(tmp_path)
    log.append(actor="tester", action=AuditAction.HUMAN_DECISION, run_id="R", note="real")
    log.append(actor="tester", action=AuditAction.HUMAN_DECISION, run_id="R", note="real")
    entries = log.entries()
    forged = entries[1].model_copy(update={"note": "not what was approved"})
    forged = forged.seal()
    import json

    row = json.loads(forged.canonical_payload())
    row["hash"] = forged.hash
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    conn.execute("DROP TRIGGER audit_entries_no_update")
    conn.execute(
        "UPDATE audit_entries SET payload=? WHERE seq=2",
        (json.dumps(row, sort_keys=True, separators=(",", ":")),),
    )
    conn.commit()
    result = verify_log(log)
    assert result.ok is False
    assert result.first_broken_seq == 2
    assert "do not match" in result.message

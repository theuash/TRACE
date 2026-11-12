"""Verifier for the audit chain.

Independent of the writer: it re-derives every hash from the stored fields and compares. Any edited
value, reordered row, dropped row or truncated tail is reported with the first broken sequence
number.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from shared.schemas import GENESIS_HASH, AuditEntry, AuditVerification

if TYPE_CHECKING:
    from audit.log import AuditLog


def _fail(seq: int, checked: int, message: str) -> AuditVerification:
    return AuditVerification(
        ok=False, entries_checked=checked, first_broken_seq=seq, message=message
    )


def verify_chain(entries: Sequence[AuditEntry]) -> AuditVerification:
    prev = GENESIS_HASH
    for expected_seq, entry in enumerate(entries, start=1):
        checked = expected_seq - 1
        if entry.seq != expected_seq:
            return _fail(entry.seq, checked, f"row {entry.seq} is out of place")
        if entry.prev_hash != prev:
            msg = f"row {entry.seq}: prev_hash does not match the row before it"
            return _fail(entry.seq, checked, msg)
        if entry.compute_hash() != entry.hash:
            msg = f"row {entry.seq}: contents do not match the stored hash"
            return _fail(entry.seq, checked, msg)
        prev = entry.hash
    return AuditVerification(
        ok=True,
        entries_checked=len(entries),
        message=f"{len(entries)} entries verified; chain intact",
    )


def verify_log(log: AuditLog) -> AuditVerification:
    """Same checks as `verify_chain`, but a row that cannot even be read is itself a finding."""
    prev = GENESIS_HASH
    for idx, (seq, payload, stored_hash) in enumerate(log.raw_entries(), start=1):
        try:
            entry = AuditEntry.model_validate_json(payload)
        except Exception:  # noqa: BLE001 - corrupt bytes are the thing we are looking for
            return _fail(seq, idx - 1, f"row {seq}: stored row is not a valid audit entry")
        entry = entry.model_copy(update={"hash": stored_hash})
        if entry.seq != seq:
            return _fail(seq, idx - 1, f"row {seq} is out of place")
        if entry.prev_hash != prev:
            msg = f"row {seq}: prev_hash does not match the row before it"
            return _fail(seq, idx - 1, msg)
        if entry.compute_hash() != entry.hash:
            return _fail(seq, idx - 1, f"row {seq}: contents do not match the stored hash")
        prev = entry.hash
    return AuditVerification(
        ok=True,
        entries_checked=len(log.raw_entries()),
        message=f"{len(log.raw_entries())} entries verified; chain intact",
    )

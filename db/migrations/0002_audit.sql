-- The audit log: one sealed row per decision, never rewritten.
-- `payload` is the canonical JSON of the AuditEntry, `hash` its SHA-256 over that payload.

CREATE TABLE IF NOT EXISTS audit_entries (
    seq     BIGINT PRIMARY KEY,
    payload TEXT NOT NULL,
    hash    TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS audit_entries_hash_idx ON audit_entries (hash);

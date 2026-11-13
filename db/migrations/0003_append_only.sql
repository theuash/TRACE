-- Two independent layers stop history being rewritten (same guarantee as the old SQLite file):
--   1. triggers that raise on any UPDATE or DELETE of a row,
--   2. the hash chain itself: every row stores the hash of the row before it, so even a
--      change that bypassed the database would be detectable by audit/verify.py.

CREATE OR REPLACE FUNCTION audit_entries_forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit log is append-only: % is forbidden', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_entries_no_update ON audit_entries;
CREATE TRIGGER audit_entries_no_update
    BEFORE UPDATE ON audit_entries
    FOR EACH ROW EXECUTE FUNCTION audit_entries_forbid_mutation();

DROP TRIGGER IF EXISTS audit_entries_no_delete ON audit_entries;
CREATE TRIGGER audit_entries_no_delete
    BEFORE DELETE ON audit_entries
    FOR EACH ROW EXECUTE FUNCTION audit_entries_forbid_mutation();

-- Belt and braces: nobody but the owner may write, and no role may change a sealed row.
REVOKE UPDATE, DELETE ON audit_entries FROM PUBLIC;

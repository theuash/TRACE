-- TRUNCATE is not covered by the row triggers above, and it would wipe the whole chain.
-- The demo reset path disables the trigger explicitly (see api/main.py) - nobody else can.

CREATE OR REPLACE FUNCTION audit_entries_forbid_truncate() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit log is append-only: TRUNCATE is forbidden'
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_entries_no_truncate ON audit_entries;
CREATE TRIGGER audit_entries_no_truncate
    BEFORE TRUNCATE ON audit_entries
    FOR EACH STATEMENT EXECUTE FUNCTION audit_entries_forbid_truncate();

REVOKE TRUNCATE ON audit_entries FROM PUBLIC;

-- Core tables: the runs the workflow knows about, the live policy, and the idempotency ledger.
-- Money stays exact: NUMERIC, never FLOAT.

CREATE TABLE IF NOT EXISTS runs (
    run_id     TEXT PRIMARY KEY,
    ticker     TEXT NOT NULL,
    status     TEXT NOT NULL,
    error      TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs (created_at);
CREATE INDEX IF NOT EXISTS runs_ticker_idx ON runs (ticker);

-- Small key/value store for the live thresholds (the workflow writes them, the API reads them).
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Side effects that already ran, keyed by (run_id, step, item_id).
-- This is what makes a resumed run skip work it has already done.
CREATE TABLE IF NOT EXISTS side_effects (
    run_id     TEXT NOT NULL,
    step       TEXT NOT NULL,
    item_id    TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, step, item_id)
);

CREATE INDEX IF NOT EXISTS side_effects_run_idx ON side_effects (run_id);

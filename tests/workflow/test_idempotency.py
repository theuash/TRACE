from workflow.idempotency import IdempotencyStore


def test_side_effect_runs_once_and_replays(postgres):
    store = IdempotencyStore(postgres.dsn, schema=postgres.schema)
    calls = {"n": 0}

    def effect():
        calls["n"] += 1
        return {"answer": 42}

    first = store.run_once("R1", "fetch_filing", "run", effect)
    second = store.run_once("R1", "fetch_filing", "run", effect)
    assert calls["n"] == 1
    assert first == {"answer": 42}
    assert second == first  # replayed from the ledger, never executed again
    assert store.counts("R1") == {"fetch_filing": 1}

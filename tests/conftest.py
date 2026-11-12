import pytest

from shared.config import get_settings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own data dir, audit DB, checkpoint DB and fake providers."""
    monkeypatch.setenv("USE_FAKES", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))
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

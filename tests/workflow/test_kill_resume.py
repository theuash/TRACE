"""The mandatory test: a paused run survives a process kill and repeats nothing.

Two separate processes share only SQLite on disk. The first one starts a run and exits (the pause is
a hard kill from the outside world's point of view). The second one resumes it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = Path(__file__).parent / "scripts" / "kill_resume_phase.py"


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "P2_TEST_DATA": str(tmp_path),
        "USE_FAKES": "true",
        "DATA_DIR": str(tmp_path),
        "AUDIT_DB_PATH": str(tmp_path / "audit.db"),
        "SEC_USER_AGENT": "Kill Resume Test test@example.com",
    }


def _run(*args: str, tmp_path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=_env(tmp_path),
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.slow
def test_paused_run_survives_a_process_kill_and_repeats_nothing(tmp_path):
    started = _run("start", tmp_path=tmp_path)
    assert started["counts"] == {"fetch_filing": 1, "extract": 1}

    resumed = _run("resume", json.dumps(started), tmp_path=tmp_path)

    assert resumed["status"] == "completed"
    for step in ("fetch_filing", "extract"):
        assert resumed["counts"][step] == 1, "a side effect ran twice after the kill"
    assert resumed["audit"] == 9
    assert resumed["verify"] is True

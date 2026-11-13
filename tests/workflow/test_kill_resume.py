"""The mandatory test: a paused run survives a process kill and repeats nothing.

Two separate processes share only the database. The first one starts a run and exits (the pause is
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


def _env(postgres) -> dict[str, str]:
    return {
        **os.environ,
        "USE_FAKES": "true",
        "SEC_USER_AGENT": "Kill Resume Test test@example.com",
        "TRACE_TEST_DSN": postgres.dsn,
        "TRACE_TEST_SCHEMA": postgres.schema,
    }


def _run(*args: str, postgres) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=_env(postgres),
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.slow
def test_paused_run_survives_a_process_kill_and_repeats_nothing(db_context):
    started = _run("start", postgres=db_context)
    assert started["counts"] == {"fetch_filing": 1, "extract": 1}

    resumed = _run("resume", json.dumps(started), postgres=db_context)

    assert resumed["status"] == "completed"
    for step in ("fetch_filing", "extract"):
        assert resumed["counts"][step] == 1, "a side effect ran twice after the kill"
    assert resumed["audit"] == 9
    assert resumed["verify"] is True

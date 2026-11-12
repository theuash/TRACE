"""One phase of the kill-and-resume test. Run it in two separate processes.

python kill_resume_phase.py start
python kill_resume_phase.py resume '{"run_id": "..."}'
"""

import json
import os
import sys
from pathlib import Path

from shared.schemas import DecisionType, ReviewDecision, ReviewStatus, RunRequest
from workflow.service import WorkflowService

DATA = Path(os.environ["P2_TEST_DATA"])
svc = WorkflowService(DATA / "runs.db", DATA / "ckpt.db")
phase = sys.argv[1]

if phase == "start":
    run = svc.start_runs(RunRequest(tickers=["AAPL"]))[0]
    print(json.dumps({"run_id": run.run_id, "counts": run.side_effect_counts}))
else:
    run_id = json.loads(sys.argv[2])["run_id"]
    run = svc.get_run(run_id)
    for review in svc.list_reviews(ReviewStatus.PENDING):
        svc.submit_decision(
            ReviewDecision(
                review_id=review.review_id, decision=DecisionType.APPROVE, reviewer="tester"
            )
        )
    print(
        json.dumps(
            {
                "status": svc.get_run(run_id).status.value,
                "counts": run.side_effect_counts,
                "audit": len(svc.list_audit()),
                "verify": svc.verify_audit().ok,
            }
        )
    )

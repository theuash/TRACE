"""One phase of the kill-and-resume test. Run it in two separate processes.

python kill_resume_phase.py start
python kill_resume_phase.py resume '{"run_id": "..."}'

The two processes share only the database: the run, its side effects and the audit chain live
in PostgreSQL, so a hard kill between the phases loses nothing.
"""

import json
import os
import sys

from shared.schemas import DecisionType, ReviewDecision, ReviewStatus, RunRequest
from workflow.service import WorkflowService

DSN = os.environ["TRACE_TEST_DSN"]
SCHEMA = os.environ["TRACE_TEST_SCHEMA"]

import audit.log as audit_log
from audit.log import AuditLog
from workflow.idempotency import IdempotencyStore

# The two phases are separate processes: point the singletons at the test schema.
audit_log._DEFAULT = AuditLog(DSN, schema=SCHEMA)
import workflow.idempotency as idem

idem._STORE = IdempotencyStore(DSN, schema=SCHEMA)

svc = WorkflowService(DSN, schema=SCHEMA)
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

# API contract for `trace-ui` (backend)

From: Person 2 · To: Person 3 · Branch: `contract/p2-nullable-escalation-value`

`trace-ui` is the dashboard. It already has two modes (`VITE_API_MODE=mock|http`); this is the
contract for `http`, so `api/main.py` is a thin FastAPI wrapper over `workflow.service.get_service()`.

## Endpoints

| Method | Path | Backend source |
|---|---|---|
| GET | `/health` | constant |
| GET | `/companies` | `shared.config.COMPANIES` |
| POST | `/audits` | `service.start_runs(RunRequest(...))` |
| GET | `/threads` | `service.list_runs()` |
| GET | `/threads/{id}/status` | aggregate below |
| GET | `/threads/{id}/timeline` | `service.get_timeline(run_id)` (added by me) |
| POST | `/threads/{id}/resume` | `service.submit_decision(ReviewDecision)` |
| GET | `/audit-logs` | `service.list_audit()` + filters |
| GET | `/audit-logs/verify` | `service.verify_audit()` |
| POST | `/demo/reset` | delete runs in `data/runs.db` |
| POST | `/demo/tamper` | deliberately corrupt one audit row |
| POST | `/demo/failure-mode` | `workflow/fault.py` FaultSpec on the next run |

## `GET /threads/{id}/status`

`trace-ui/src/api/types.ts:174` is the source of truth. Compose it from one service call:

```python
{
  "thread_id": run.run_id,            # RunSummary.run_id
  "status": run.status.value,         # RunSummary.status
  "metrics": [...],                   # service.list_metrics(ticker)  -> ExtractedMetric
  "validation_checks": [...],         # service.list_validations(ticker)
  "flagged_items": [...],             # service.list_reviews(ReviewStatus.PENDING) -> EscalationItem
  "accuracy_report": service.get_report(),
  "thresholds": service.get_thresholds().model_dump(),
  "fiscal_year": ..., "period_end": ..., "cik": ...   # from state["extraction"]["filing"]
  "anomaly_explanations": {metric_id: validation.explanation}
}
```

`flagged_items[].reasons` is `EscalationReason.message`; `severity` comes from `RiskTier`.
`EscalationItem.value` is `Decimal | None` (contract change) — a missing metric is `null`, never `0`.

## `POST /threads/{id}/resume`

Body is a `ReviewDecision`. A `Red` item **cannot** be approved without a note; the service raises
`ValueError`, return it as HTTP 422 with `detail`. Do not catch it and pretend success.

## Hard rules

1. `/demo/tamper` and `/demo/reset` must be refused unless a demo flag is set. Tampering defeats
   audit rule 5 (append-only hash chain) and must never be reachable in a real run.
2. Every endpoint reads through `get_service()`; never import `validation/` or `workflow/` internals.
3. No secrets in responses. Do not echo `.env` values.

## Definition of done

```bash
cd trace-ui && VITE_API_MODE=http npm run dev
uv run uvicorn api.main:app --reload --port 8000
```

The review queue shows the real AAPL run (metrics, tiers, evidence) from the backend, and
`npm run test:e2e` passes against http mode.

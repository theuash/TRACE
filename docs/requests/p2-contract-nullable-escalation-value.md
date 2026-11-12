# Contract request: `EscalationItem.value` must be nullable

From: Person 2 · To: Person 1, Person 3 · Branch: `contract/p2-nullable-escalation-value`

## The problem

A core metric can be **absent** from a filing. Today `decide()` iterates `result.metrics`, so a
missing metric produces no `EscalationItem` at all, and a run can look clean while 4 of 8 core
metrics do not exist. `EscalationItem.value` was `Decimal` (required), so there was nothing honest
to put in an item for a value that was never found.

Real example, AAR Corp FY2026 (10-K as filed): `revenue`, `total_assets`, `total_liabilities`,
`shareholders_equity` were all missing. `accounting_equation` failed with severity `error`, and
before this change **nothing** reached Red.

## The change (additive, one line + comment)

`shared/schemas.py`

```python
value: Decimal | None = None   # was: value: Decimal
```

Rules attached to it:

- `None` means **not present in the filing**. It is never `0` — `0` is a real value and hard rule 6
  forbids inventing one.
- A missing core metric is always `tier=RED`, `confidence=0.0`,
  `reasons[0].kind == EscalationKind.MISSING_VALUE` (enum value already existed, unchanged).
- `review_id` = `make_metric_id(ticker, metric, fiscal_year)`, so it is stable and correlates with
  `ExtractedMetric.id` when a reviewer corrects the value by hand.

## Impact on you

**Person 3 (API/UI):** `EscalationItem.value` may be `None`. Render it as "not found", never as
`0` and never with a `$` prefix. `AuditEntry.original_value` was already nullable, so audit rows
are unaffected. No `api/` or `ui/` code exists yet, so nothing breaks today.

**Person 1 (extraction):** no change required. This makes your `warnings` list
("Metrics not found in the filing: …") machine-actionable instead of a string.

## Verified

- `tests/validation/test_decide.py::test_missing_core_metric_is_red_and_carries_no_value`
- Full run: `tests/workflow tests/audit tests/validation` → 25 passed
- Live, on real data: 9 escalations → 4 Red (`value=None`) + 5 Yellow.

## Approval

- [ ] Person 1
- [ ] Person 3

Merge to `main` only after both tick.

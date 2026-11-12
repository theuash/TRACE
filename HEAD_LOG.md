# HEAD_LOG

## 2026-11-12 — branch `contract/p2-nullable-escalation-value`: missing metrics, learned labels

Changed: `shared/schemas.py` (`EscalationItem.value: Decimal | None`), `validation/decide.py`
(missing core metric → Red, `value=None`), `workflow/service.py` (a failed resume is recorded on the
run; `RunSummary.error` was never read from the DB), `extraction/alias_memory.py` (new; labels the
model taught us, SQLite at `data/aliases.db`), `extraction/table_parser.py` (fallback tier is
prefix-only — `Deferred revenue` no longer matches `revenue`), `extraction/pipeline.py` +
`llm/second_reader.py` (`read_labels`: the model names a row, the parser supplies the number),
`extraction/__main__.py` (`--aliases`), tests, and `docs/requests/`.

Why: a run could report 1 auto-approved / 5 escalated while 4 of 8 core metrics were absent and the
accounting equation had failed at severity `error`. Separately, the greedy `alias in label` tier
produced a wrong revenue at confidence 0.86, which auto-approved.

Restart: `person1` and `person3` must restart OpenCode (contract field changed; P3 renders
`EscalationItem.value`). `person2` also, to load the new rules.
Approval boxes in `docs/requests/p2-contract-nullable-escalation-value.md` are still unticked.

Not run: any git command.


## 2026-11-12 — P2 stack implemented, contract delta, git policy acknowledged

Changed: `shared/schemas.py` (additive: `RiskTier`, `Thresholds.confidence_critical=0.60`,
`EscalationItem.tier`), `workflow/` (fakes, graph, service, fault, idempotency), `audit/` (log, verify),
`validation/` (checks, engine, decide), `tests/` (27 tests incl. kill-and-resume), `PLAN_P2.md`,
`pyproject.toml` (pytest marker), plus the docs/rules clarifications in `VISION.md`, `AGENTS.md`,
`README.md`, `shared/interfaces.py` docstring, `.gitignore`, and the three person agent files.

Why: the human asked for the Person 2 plan and its implementation; confidence needed one definition
(deterministic parse quality, not model certainty) everywhere.

Restart: `person1`, `person2`, `person3` sessions must be restarted to load the new rules. HEAD
already has them.

Not run: any git command. The human runs git; suggested messages are in the chat history.

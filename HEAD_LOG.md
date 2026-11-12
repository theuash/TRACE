# HEAD_LOG

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

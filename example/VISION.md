# VISION

## One sentence

An autonomous financial auditor that **handles the routine, stops at the uncertain, and can prove every decision it made.**

> Automate the routine. Escalate the uncertain. Keep every decision accountable.

## The problem

One wrong number in a financial report can become a misstatement. Humans are slow and error-prone at volume. Pure
automation is fast but cannot be trusted blindly. The real need is a system that knows **when it doesn't know**.

## What we are building

A LangGraph agent that, for real companies' 10-K filings:

1. Fetches the filing from SEC EDGAR.
2. Extracts 8+ metrics from the **document itself**, keeping period, unit and source evidence.
3. Gives every value an honest **confidence score**.
4. Validates with accounting rules (Assets = Liabilities + Equity, segment sums, year-on-year jumps).
5. **Auto-approves** safe values and **pauses** on doubtful ones.
6. Lets a human approve, correct or reject, then **resumes from the saved checkpoint** with no repeated work.
7. Grades itself against the SEC XBRL "answer key".
8. Records every human decision in a **tamper-evident, append-only log**.

## The main thing: trust, made visible

| The judges should believe | Because we showed them |
|---|---|
| "It catches real errors." | A deliberately corrupted number caught and escalated live |
| "It never loses its place." | A server killed mid-review, restarted, and resumed with zero repeated actions |
| "Its confidence means something." | A calibration chart: high-confidence values really are more accurate against XBRL |
| "Nobody can quietly rewrite history." | A hash-chained audit log with a verify button |

## Principles

1. **Honest ground truth.** Extract from the filing, verify against XBRL. Never extract from the answer key.
2. **Deterministic first.** Plain code does what it can do reliably. The LLM is a fallback and an explainer.
3. **Escalate with reasons.** Every flag says why, in plain English, with the evidence beside it.
4. **Reliability over features.** A smaller system that never breaks beats a bigger one that sometimes does.
5. **Accountability by design.** Nothing a human decided can be edited afterwards.
6. **Honest limits.** We say exactly what we cover: 5 companies, 8+ metrics, HTML filings.

## How three people build it without colliding

Each person owns whole folders end to end: **Person 1** extraction, **Person 2** workflow + audit + validation,
**Person 3** verification + API + dashboard. We meet only through frozen contracts in `shared/`, and each of us has a
fake or mock to work against, so nobody waits for anybody.

## Scope

**In (mandatory):** EDGAR for 5 companies, 8+ metrics with period/unit/evidence, confidence scoring with configurable
thresholds, three validation checks, pause/resume with checkpointing, reviewer dashboard, XBRL accuracy report, append-only
audit log.

**In (wow layer, priority order):** fault injection button, kill-and-resume demo, click-to-evidence highlighting,
hash-chained log with verify button, scoreboard with calibration chart, adaptive thresholds, MCP tool wrappers.

**Out:** PDF filings, non-US filers, Docker/Postgres/Redis, vector DB or RAG, user accounts, cloud deployment.

## Success metrics (the scoreboard)

- Extraction accuracy vs XBRL (target: above 95% on required metrics)
- Auto-approved vs escalated counts
- **Escalation precision**: share of escalations that were real errors or anomalies
- Calibration: accuracy of high- vs low-confidence buckets
- Resume correctness: every `side_effect_counts` value stays 1 across a kill-and-restart
- Audit integrity: chain verifies; tampering is detected

## Definition of done

- [ ] 5 companies run end to end
- [ ] 8+ metrics per company with period, unit, evidence
- [ ] An escalation is shown, reviewed and resumed live
- [ ] Kill-and-resume test passes
- [ ] Fault injection is caught and escalated
- [ ] XBRL accuracy report and calibration chart generated
- [ ] Audit log verifies, and a tampered row is detected
- [ ] Demo works offline from cached data
- [ ] Backup recording exists

## Demo story (5 minutes)

1. **Hook (20s):** "One wrong number can mean a misstatement."
2. **Happy path (60s):** 5 companies processed, most values auto-approved.
3. **Catch (90s):** corrupt a value; the check fails; the agent pauses; the reviewer sees evidence and reason, corrects it.
4. **Reliability (60s):** kill the server while paused, restart, submit the decision, the run continues with no repeats.
5. **Accountability (30s):** the audit log shows the decision; verify integrity.
6. **Scoreboard (40s):** accuracy, escalation precision, calibration chart.
7. **Close (20s):** "Automate the routine. Escalate the uncertain. Keep every decision accountable."

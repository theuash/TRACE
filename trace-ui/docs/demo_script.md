# TRACE UI — Demo Script

## Objective

A first-time viewer should understand a flagged value, see the evidence, decide, and see the audit
entry — all within about 30 seconds, with no explanation required.

Tagline: **Automate the routine. Escalate the uncertain. Keep every decision accountable.**

## Preconditions

- `npm install` complete.
- `VITE_API_MODE=mock` (default).
- No backend required.

## Script

### 0. Landing (Overview)

1. Open `http://localhost:5173/`.
2. Read the tagline and the "Demo data" pill.
3. Note the KPI row: pending reviews, completed, auto-approved, escalated, accuracy, precision.

### 1. Launch an audit (New audit)

1. Go to `/new`.
2. Pick a company card (Apple is pre-selected for the demo flow).
3. Leave thresholds at defaults (confidence 85%, YoY 30%).
4. Leave "Demo: force pause" off (Apple is flagged anyway).
5. Click **Run audit**.
6. Wait for the live nine-step workflow stepper; observe **"Paused at checkpoint"**.
7. Click **Open review queue**.

### 2. Inspect the flagged value (Review queue)

1. The flagged item should be visible: left list + right detail.
2. Read the plain-English reason.
3. Hover the confidence bar to see the `confidence_signals` breakdown.
4. Read the source snippet; the money value should be highlighted.
5. Note the AI-generated explanation is labelled *"AI-generated, unverified"*.

### 3. Decide

1. Click **Approve** (or **Correct** with a value, or **Reject** + note).
2. Approve must be disabled until a correction or note is entered — verify.
3. Submit decisions (`Submit decisions (n)`).
4. Watch the queue progress and the thread complete.

### 4. See accuracy

1. Go to `/accuracy`.
2. Confirm final vs. original accuracy, auto-approval accuracy, escalation precision.
3. Toggle "Include demo-only runs" if needed.

### 5. Verify the audit chain

1. Go to `/audit`.
2. Click **Verify chain**.
3. Expect green: *"Chain intact — N of N records verified."*

### 6. Close

1. Return to `/overview`.
2. Confirm the thread now shows completed and accuracy.

## Timing budget

| Step | Target |
|---|---|
| Launch audit → paused | ≤ 10s |
| Queue → decide → submit | ≤ 15s |
| Accuracy visible | ≤ 5s |
| Verify chain | ≤ 5s |
| Total | **≤ 30s** |

## Recording plan

See `docs/backup-recording-plan.md`.

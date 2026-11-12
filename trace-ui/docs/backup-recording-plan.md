# TRACE UI — Backup / Recording Plan

## Purpose

How the TRACE UI demo state and artifacts are backed up and recorded, so a
judge/audience can reproduce the demo without redoing the setup.

## Demo state

- Mock server state lives in `localStorage` keys `trace.mock.threads.v1` and
  `trace.mock.logs.v1`. Clearing site data resets demo data (Settings → Reset demo data).

## Reset procedure

1. Open the app.
2. Go to `/settings`.
3. Open the Danger zone.
4. Click **Reset demo data**.
5. Confirm in the dialog.

## Recording the demo

- Capture a screen recording (OBS / QuickTime / built-in screen recorder) of:
  1. Overview.
  2. New audit → Run audit → Paused at checkpoint.
  3. Review queue → flagged item → Approve → Submit decisions.
  4. Accuracy.
  5. Audit log → Verify chain.
- Keep the recording under 2 minutes; export as MP4 + poster frame.

## Backup of local dev artifacts

- Do **not** commit `node_modules/`, `dist/`, `.env`, or any browser profile data.
- `.gitignore` covers these; keep it that way.

## Restore / re-seed

- The mock server re-seeds from in-code fixtures on first load when localStorage is empty.
- No external backup of fixtures is required; fixtures are version-controlled source.

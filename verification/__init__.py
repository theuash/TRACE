"""Person 3: XBRL ground truth and the accuracy report.

Nothing outside this package may call Company Facts. See `VISION.md` rule 1.
"""

from __future__ import annotations

from verification.ground_truth import verify_company
from verification.report import build_report

__all__ = ["build_report", "verify_company"]

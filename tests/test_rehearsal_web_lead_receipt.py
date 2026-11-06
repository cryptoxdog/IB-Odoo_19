"""Gate 5 scores the controller selection value, not the HOT label.

Pure-python tier. The rehearsal script is read as text. A real hot
classification returns decision ``hot`` and finishes at ``intake_created``.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "tests" / "production-rehearsal" / "weblead_e2e.sh"

# The old failure was ``decision=hot (expected HOT)``. The comparison that
# produced it bound the decision field to the display label.
_DECISION_LABEL = re.compile(r'\$\{DECISION\}"\s*(?:!=|==)\s*"HOT"')


def test_rehearsal_web_lead_receipt_uses_selection_value():
    text = GATE.read_text(encoding="utf-8")
    assert "expected HOT" not in text
    assert _DECISION_LABEL.search(text) is None
    assert '[ "${DECISION}" != "hot" ]' in text
    assert '[ "${STATE}" != "intake_created" ]' in text

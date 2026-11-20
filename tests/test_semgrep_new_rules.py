"""The new SQL rules stay advisory, and the PR-fast lane can see their fixtures.

The rule file and the XML fixture are not production Python. A test that reads
both is the structural consumer for this branch. Semgrep itself stays in
``make semgrep-test``; this contract only reads the files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.adversarial_contract

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".semgrep" / "odoo-patterns.yml"
XML = ROOT / ".semgrep" / "tests" / "odoo19.xml"

NEW_RULES = (
    "plasticos-sql-indirect-interpolation",
    "plasticos-sql-request-query",
    "plasticos-request-search-domain",
)
LEGACY_RULES = (
    "plasticos-sql-fstring-execute",
    "plasticos-python-bare-except",
)


def _block(text: str, rule_id: str) -> str:
    marker = f"- id: {rule_id}\n"
    start = text.find(marker)
    assert start >= 0, rule_id
    rest = text[start + len(marker) :]
    nxt = rest.find("\n  - id:")
    return rest if nxt < 0 else rest[:nxt]


def test_new_sql_rules_stay_advisory_and_the_xml_fixture_is_present() -> None:
    """Unadmitted rules stay WARNING, and the XML fixture remains in the tree."""
    text = RULES.read_text(encoding="utf-8")
    for rule_id in NEW_RULES:
        block = _block(text, rule_id)
        assert "severity: WARNING" in block, rule_id
        assert "plasticos_gate: review" in block, rule_id
        assert "severity: ERROR" not in block, rule_id
        assert "plasticos_gate: pr-check" not in block, rule_id
    for rule_id in LEGACY_RULES:
        assert "severity: ERROR" in _block(text, rule_id), rule_id
    assert "<" in XML.read_text(encoding="utf-8")

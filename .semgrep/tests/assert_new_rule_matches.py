#!/usr/bin/env python3
"""Per-rule proof for the new SQL and domain Semgrep rules.

An aggregate non-empty scan is not enough: each new rule must match the
positive fixture and miss the negative fixture. Removing the rule or its
positive example drops that rule id and this script exits non-zero.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / ".semgrep" / "odoo-patterns.yml"
POSITIVE = ROOT / ".semgrep" / "tests" / "positive.py"
NEGATIVE = ROOT / ".semgrep" / "tests" / "negative.py"
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
PROBES = (
    'sql.SQL(f"SELECT * FROM {untrusted_table}")',
    'sql.SQL(request.params.get("query"))',
    'sql.SQL(request.params.get("statement"))',
)


def _rule_block(text: str, rule_id: str) -> str:
    marker = f"- id: {rule_id}\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"missing rule {rule_id}")
    nxt = text.find("\n  - id:", start + len(marker))
    return text[start:] if nxt < 0 else text[start:nxt]


def _severity_gate(text: str) -> None:
    for rule_id in NEW_RULES:
        block = _rule_block(text, rule_id)
        if "severity: ERROR" in block or "plasticos_gate: pr-check" in block:
            raise SystemExit(f"{rule_id} is blocking without a recorded owner admission")
        if "severity: WARNING" not in block or "plasticos_gate: review" not in block:
            raise SystemExit(f"{rule_id} is not the non-blocking review disposition")
    for rule_id in LEGACY_RULES:
        block = _rule_block(text, rule_id)
        if "severity: ERROR" not in block:
            raise SystemExit(f"existing rule {rule_id} is no longer ERROR")


def _scan(target: Path) -> set[str]:
    proc = subprocess.run(
        ["semgrep", "--json", "--quiet", "--config", str(RULES), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in {0, 1}:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"semgrep failed on {target} ({proc.returncode})")
    payload = json.loads(proc.stdout or "{}")
    found: set[str] = set()
    for result in payload.get("results") or []:
        check_id = str(result.get("check_id") or "")
        found.add(check_id.rsplit(".", 1)[-1])
    return found


def main() -> int:
    text = RULES.read_text(encoding="utf-8")
    positive = POSITIVE.read_text(encoding="utf-8")
    _severity_gate(text)
    for probe in PROBES:
        if probe not in positive:
            raise SystemExit(f"positive fixture is missing probe: {probe}")
    hits = _scan(POSITIVE)
    for rule_id in (*NEW_RULES, *LEGACY_RULES):
        if rule_id not in hits:
            raise SystemExit(f"{rule_id} did not match {POSITIVE.name}")
    quiet = _scan(NEGATIVE)
    for rule_id in NEW_RULES:
        if rule_id in quiet:
            raise SystemExit(f"{rule_id} matched the negative fixture")
    if not _scan(XML):
        raise SystemExit(f"{XML.name} produced no findings")
    print("per-rule semgrep fixtures passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

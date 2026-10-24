"""Preservation and referential conformance for the module-owned Linda BRS baseline.

These are source-integrity tests, not Odoo runtime/business-behavior tests.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "plasticos_logistics" / "business_rules"


def test_linda_brs_baseline_is_complete_and_unchanged():
    registry = json.loads((BASE / "REGISTRY.json").read_text(encoding="utf-8"))
    files = registry["brs_files"]
    assert files == [f"BRS-{n:02}.md" for n in range(1, 8)]
    for filename, expected in registry["source_sha256"].items():
        assert hashlib.sha256((BASE / filename).read_bytes()).hexdigest() == expected, filename
    rules = json.loads((BASE / "rules.json").read_text(encoding="utf-8"))
    rule_ids = [record["rule_id"] for record in rules]
    assert len(rule_ids) == len(set(rule_ids)) == 60
    assert rule_ids == registry["rule_ids"]
    owners = json.loads((BASE / "OWNER_INDEX.json").read_text(encoding="utf-8"))
    assert {entry["brs_id"] for entry in owners} == {f"BRS-{n:02}" for n in range(1, 8)}
    for entry in owners:
        actual = {r["rule_id"] for r in rules if r["family_id"] == entry["brs_id"]}
        assert actual == set(entry["rules"])
        source = (BASE / f"{entry['brs_id']}.md").read_text(encoding="utf-8")
        headings = set(re.findall(r"^### (BRS-\d{2}-R\d{3})\b", source, flags=re.M))
        assert headings == actual


def test_supersession_has_no_broken_rule_references():
    rules = json.loads((BASE / "rules.json").read_text(encoding="utf-8"))
    known_ids = {rule["rule_id"] for rule in rules}
    supersession = (BASE / "SUPERSESSION.md").read_text(encoding="utf-8")
    explicit_ids = set(re.findall(r"^\| `(BRS-\d{2}-R\d{3})` \|", supersession, flags=re.M))
    assert explicit_ids
    assert explicit_ids.issubset(known_ids)
    assert "PO-first" in supersession and "SO-first" in supersession


def test_linda_plan_binds_every_original_rule_to_work_and_source_tests():
    """BRS coverage guard only: 60 indexed source rules mapped once to a WP and witness."""
    rules = json.loads((BASE / "rules.json").read_text(encoding="utf-8"))
    plan = (BASE.parent / "LINDA_BUILD_PLAN.md").read_text(encoding="utf-8")
    section = plan.split("## 10. Binding 60-rule BRS work-package and acceptance crosswalk", 1)[1]
    section = section.split("## 11. WP00 read-only execution card", 1)[0]
    matches = re.findall(r"^\| `(BRS-\d{2}-R\d{3})` \| ([^\n]+?) \| ([^\n]+?) \| ([^\n]+?) \|$", section, flags=re.M)
    ids = [row[0] for row in matches]
    assert len(ids) == len(set(ids)) == 60
    assert ids == [r["rule_id"] for r in rules]
    allowed_work_packages = {
        "WP00",
        "WP01a",
        "WP01b",
        "WP02",
        "WP02b",
        "WP03",
        "WP04",
        "WP05",
        "WP06",
        "WP07",
        "WP08",
        "WP09",
        "WP10",
    }
    acceptance_cases = set(re.findall(r"^\| (A\d{2}) \|", plan, flags=re.M))
    assert acceptance_cases == {f"A{idx:02}" for idx in range(1, 31)}
    for row, src in zip(matches, rules):
        _, owners, witnesses, originals = row
        owners = re.findall(r"`(WP\d{2}[ab]?)`", owners)
        plan_tests = re.findall(r"`(A\d{2})`", witnesses)
        source_tests = re.findall(r"`(AC-[A-Z0-9]+)`", originals)
        assert owners and set(owners) <= allowed_work_packages, src["rule_id"]
        assert plan_tests and set(plan_tests) <= acceptance_cases, src["rule_id"]
        assert source_tests == src["tests"], src["rule_id"]
    assert "source-authorized" in plan
    assert "warehouse/pickup-site" in plan
    for required in ("BRS-02-R007", "BRS-06-R039", "BRS-07-R051"):
        assert required in plan
    supplement = (BASE / "SUPERSESSION.md").read_text(encoding="utf-8")
    for required in ("BRS-02-R004", "BRS-05-R029", "BRS-07-R047"):
        assert re.search(r"^\| `" + required + r"` \|", supplement, flags=re.M)

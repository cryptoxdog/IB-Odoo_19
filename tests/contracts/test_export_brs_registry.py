"""Preservation and referential conformance for the module-owned Export BRS baseline.

Mirrors tests/contracts/test_logistics_brs_registry.py. These are source-integrity
tests, not Odoo runtime or business-behavior tests. REGISTRY.json records, per
copy, its SHA-256, its pack source's SHA-256 and whether end-of-file normalization
changed it. Repository tests do not read the campaign pack
(tests/test_no_campaign_file_dependency.py); the copy-to-source comparison is a
recorded validation step of the slice that registers the copies.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "plasticos_export" / "business_rules"
CHAPTERS = [f"BRS-EXP-{n:02}" for n in range(1, 15)]
RULE_ID = r"BRS-EXP-\d{2}-R\d{3}"
SLICES = {"S2", "S3", "S4", "S5", "S6", "PHASE2"}


def _json(name: str):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def _rules() -> list[dict]:
    return _json("rules.json")["rules"]


def test_export_brs_baseline_is_complete_and_unchanged():
    registry = _json("REGISTRY.json")
    assert registry["brs_files"] == [f"{chapter}.md" for chapter in CHAPTERS]
    preserved = {f"{chapter}.md" for chapter in CHAPTERS} | {"rules.json", "ACCEPTANCE.json"}
    copies = registry["copies"]
    assert set(copies) == preserved
    for filename, entry in copies.items():
        data = (BASE / filename).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["copy_sha256"], filename
        # The only permitted difference from the pack source is end-of-file
        # normalization: exactly one terminal newline.
        assert data.endswith(b"\n") and not data.endswith(b"\n\n"), filename
        assert entry["normalized"] is (entry["copy_sha256"] != entry["source_sha256"]), filename
        assert re.fullmatch(r"[0-9a-f]{64}", entry["source_sha256"]), filename
    rules = _rules()
    rule_ids = [rule["id"] for rule in rules]
    assert len(rule_ids) == len(set(rule_ids)) == 120
    assert rule_ids == registry["rule_ids"]
    owners = _json("OWNER_INDEX.json")
    assert [entry["brs_id"] for entry in owners] == CHAPTERS
    for entry in owners:
        expected = [rule["id"] for rule in rules if rule["chapter"] == entry["brs_id"]]
        assert entry["rules"] == expected, entry["brs_id"]
        source = (BASE / f"{entry['brs_id']}.md").read_text(encoding="utf-8")
        headings = re.findall(rf"^### ({RULE_ID})\b", source, flags=re.M)
        assert headings == expected, entry["brs_id"]


def test_every_rule_has_its_one_acceptance_case():
    acceptance = _json("ACCEPTANCE.json")
    cases = acceptance["cases"]
    assert acceptance["case_count"] == len(cases) == 120
    by_rule = {case["rule_id"]: case for case in cases}
    assert len(by_rule) == 120
    for rule in _rules():
        case = by_rule[rule["id"]]
        assert case["id"] == rule["acceptance_id"], rule["id"]
        assert case["status"] == "NOT_RUN", rule["id"]


def test_supersession_has_no_broken_rule_references():
    known_ids = {rule["id"] for rule in _rules()}
    supersession = (BASE / "SUPERSESSION.md").read_text(encoding="utf-8")
    explicit_ids = set(re.findall(rf"^\| `({RULE_ID})` \|", supersession, flags=re.M))
    assert explicit_ids
    assert explicit_ids <= known_ids
    mentioned = set(re.findall(RULE_ID, supersession))
    assert mentioned <= known_ids
    assert re.findall(r"`(SUPERSESSION_v1_\d\.md)`", supersession)


def test_every_rule_maps_once_to_a_slice_and_a_witness():
    rules = _rules()
    with (BASE / "BUSINESS_RULE_TRACEABILITY.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["rule_id"] for row in rows]
    assert len(ids) == len(set(ids)) == 120
    assert ids == [rule["id"] for rule in rules]
    for row, rule in zip(rows, rules):
        assert row["slice"] in SLICES, row["rule_id"]
        assert row["slice_basis"], row["rule_id"]
        assert row["witness_acceptance_id"] == rule["acceptance_id"], row["rule_id"]
        assert (row["slice"] == "PHASE2") == (rule["phase"] == "P2"), row["rule_id"]


def test_effective_rules_render_the_registered_statements():
    rules = _rules()
    effective = _json("EFFECTIVE_RULES.json")
    assert effective["origin_source_sha256"] == hashlib.sha256((BASE / "rules.json").read_bytes()).hexdigest()
    assert [entry["id"] for entry in effective["rules"]] == [rule["id"] for rule in rules]
    for entry, rule in zip(effective["rules"], rules):
        assert entry["normative_text"] == rule["statement"], rule["id"]
        assert entry["effective_in_phase_1"] == (rule["phase"] != "P2"), rule["id"]
    rendered = (BASE / "EFFECTIVE_RULES.md").read_text(encoding="utf-8")
    assert re.findall(rf"^### ({RULE_ID}) ", rendered, flags=re.M) == [rule["id"] for rule in rules]

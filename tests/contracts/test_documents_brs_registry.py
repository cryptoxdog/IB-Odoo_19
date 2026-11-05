"""Ownership split for the seven Linda external-send clauses, with frozen chapter bytes."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCUMENTS = REPO / "plasticos_documents" / "business_rules"
TRANSFERRED = [f"BRS-POS-09-R{number:03d}" for number in range(6, 13)]
EXTERNAL_SEND_OWNER = "plasticos_logistics (Linda external send); Documents and Activities supply status only"
EXCEPTION = (
    "The dated supersession of 2026-11-05 admits exactly one copied Native-First chapter, "
    "BRS-POS-10, and admits BRS-POS-09-R006 through BRS-POS-09-R012 as Linda external-send obligations."
)
DOCUMENTS_SENTENCE = (
    "External-send ownership of BRS-POS-09-R006 through BRS-POS-09-R012 moved to "
    "`plasticos_logistics` by the dated supersession"
)
CHAPTER_SHA256 = {
    "BRS-POS-02-native-documents-originals-and-intake.md": (
        "5d3400f2df8fdfc844357f6c73c1f3c66ca360e31034b8401c6ea0c4d3ffb2dd"
    ),
    "BRS-POS-03-evidence-classification-attribution-and-verification.md": (
        "38311773cf2665c574246a1f1ab447be7f0a04731162d767f729bafeaf3d3dd8"
    ),
    "BRS-POS-09-native-documents-requests-activities-automation-and-scheduler.md": (
        "539f9226de1133756da7d816e9b4e1f38d80ccd226998487925859f44aa14efd"
    ),
}
MARKER_SHA256 = {
    "plasticos_logistics/AGENTS.md": "698842d67b3b704e35fdeba4cb1153afaf7493f328835dd59ef9fb6967a2749f",
    "plasticos_logistics/business_rules/README.md": (
        "758ae4f359ca2fb31b806fdb86a627d427b63ea2f02034c5731678d0be45a338"
    ),
}
BEGIN = "<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_BEGIN -->"
END = "<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_END -->"


def _marker_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8")
    start = text.index(BEGIN)
    stop = text.index(END) + len(END)
    return text[start:stop].encode()


def test_documents_scope_splits_installed_text_from_external_send_owner():
    with (DOCUMENTS / "ALL_170_RULES_SCOPE.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    local = [row["rule_id"] for row in rows if row["scope"] == "DOCUMENTS_BRS_LOCAL"]
    assert len(local) == 37
    assert not set(TRANSFERRED) & set(local)
    by_id = {row["rule_id"]: row for row in rows}
    for rule_id in TRANSFERRED:
        assert by_id[rule_id]["scope"] == "CROSS_DOMAIN_CONSUMER_REFERENCE"
        assert by_id[rule_id]["source_semantic_owner"] == EXTERNAL_SEND_OWNER

    registry = json.loads((DOCUMENTS / "REGISTRY.json").read_text(encoding="utf-8"))
    assert len(registry["source_rule_ids"]) == 44
    assert registry["local_rule_count"] == 44
    assert registry["external_rule_count"] == 126
    assert [item["id"] for item in registry["ownership_transferred"]] == TRANSFERRED

    effective = json.loads((DOCUMENTS / "EFFECTIVE_RULES.json").read_text(encoding="utf-8"))
    owners = {rule["id"]: rule["semantic_owner"] for rule in effective["rules"]}
    for rule_id in TRANSFERRED:
        assert owners[rule_id] == EXTERNAL_SEND_OWNER
    assert owners["BRS-POS-09-R005"].startswith("Odoo Documents/Activity")
    assert owners["BRS-POS-09-R013"].startswith("Odoo Documents/Activity")


def test_documents_chapter_bytes_and_overlay_markers_stay_frozen():
    for filename, expected in CHAPTER_SHA256.items():
        digest = hashlib.sha256((DOCUMENTS / filename).read_bytes()).hexdigest()
        assert digest == expected, filename
    for relative, expected in MARKER_SHA256.items():
        digest = hashlib.sha256(_marker_bytes(REPO / relative)).hexdigest()
        assert digest == expected, relative
        text = (REPO / relative).read_text(encoding="utf-8")
        assert text.index(EXCEPTION) > text.index(END)

    for relative in (
        "plasticos_documents/AGENTS.md",
        "plasticos_documents/business_rules/README.md",
    ):
        assert DOCUMENTS_SENTENCE in (REPO / relative).read_text(encoding="utf-8")
    assert "37 rules remain Documents-owned" in (DOCUMENTS / "README.md").read_text(encoding="utf-8")
    assert "37 rules remain Documents-owned" in (REPO / "plasticos_documents/AGENTS.md").read_text(encoding="utf-8")

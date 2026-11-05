"""Provenance lock for the one Native-First chapter installed in logistics."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "plasticos_logistics" / "business_rules"
CHAPTER = "BRS-POS-10-linda-logistics-commercial-and-physical-communication.md"
SOURCE_SHA256 = "db02b9d8dba173fad42a538edcfe583b907d4763dfb49296c78b8d03e2179cc4"


def test_brs_pos_10_chapter_matches_source_pack_and_registry():
    registry = json.loads((BASE / "NATIVE_FIRST_REGISTRY.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256((BASE / CHAPTER).read_bytes()).hexdigest()
    assert digest == SOURCE_SHA256
    assert registry["chapter_sha256"] == SOURCE_SHA256
    assert registry["chapter_file"] == CHAPTER
    assert registry["admits_other_native_first_chapters"] is False
    source = (BASE / CHAPTER).read_text(encoding="utf-8")
    headings = re.findall(r"^### (BRS-POS-10-R\d{3})\b", source, flags=re.M)
    assert headings == [rule["id"] for rule in registry["rules"]]
    assert len(headings) == 16

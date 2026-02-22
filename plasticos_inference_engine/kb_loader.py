"""
plasticos_inference/kb_loader.py
Loads and indexes all YAML knowledge bases from a directory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("plasticos_inference.kb_loader")


@dataclass
class KBIndex:
    """Indexed knowledge base ready for engine queries."""

    # Keyed by normalized polymer code (e.g. "HDPE", "PP")
    material_grades: dict[str, list[dict]] = field(default_factory=dict)
    inference_rules: list[dict] = field(default_factory=list)
    recycling_rules: dict[str, list[dict]] = field(default_factory=dict)
    contamination_profiles: dict[str, list[dict]] = field(default_factory=dict)
    quality_tiers: dict[str, dict] = field(default_factory=dict)
    product_scrap_mapping: dict[str, list[dict]] = field(default_factory=dict)

    # Raw KBs for fallback access
    raw: dict[str, dict] = field(default_factory=dict)

    # Metadata
    files_loaded: list[str] = field(default_factory=list)

    @property
    def polymers(self) -> list[str]:
        return sorted(self.material_grades.keys())

    @property
    def total_grades(self) -> int:
        return sum(len(v) for v in self.material_grades.values())

    @property
    def total_rules(self) -> int:
        return len(self.inference_rules)


# Inference types we load (forward / property enrichment)
_LOAD_TYPES = {
    "property",
    "materialidentification",
    "qualityassessment",
    "processingrequirement",
    "applicationmatching",
    "qualitycontrol",
    "contaminationassessment",
    "formidentification",
}

# Inference types we skip (belong to buyer-matching or pricing)
_SKIP_TYPES = {"buyermatching", "sourcematching", "pricing"}


def load_kb(kb_dir: Path | str) -> KBIndex:
    """
    Scan *_v7.0r.yaml in kb_dir, parse, and build the index.

    Parameters
    ----------
    kb_dir : Path
        Directory containing YAML knowledge-base files.

    Returns
    -------
    KBIndex
        Fully indexed KB ready for engine consumption.
    """
    kb_dir = Path(kb_dir)
    idx = KBIndex()

    for yf in sorted(kb_dir.glob("*_v7.0r.yaml")):
        try:
            with open(yf, encoding="utf-8") as fh:
                kb = yaml.safe_load(fh)
            if not isinstance(kb, dict):
                continue
        except Exception as exc:
            logger.warning("Skipping %s: %s", yf.name, exc)
            continue

        meta = kb.get("metadata", {})
        polymer = meta.get("polymertype") or meta.get("materialtype") or meta.get("kbname") or yf.stem
        key = polymer.upper().replace(" ", "_")
        idx.raw[key] = kb
        idx.files_loaded.append(yf.name)

        # ── Material grades ──────────────────────────────────
        for grade in kb.get("materialgrades", []):
            grade["_source_file"] = yf.name
            idx.material_grades.setdefault(key, []).append(grade)

        # ── Inference rules ──────────────────────────────────
        for rule in kb.get("inferencerules", []):
            itype = (rule.get("inferencetype") or "").lower()
            rtype = (rule.get("ruletype") or "").lower()
            if itype in _SKIP_TYPES or rtype == "backward":
                continue
            rule["_polymer"] = key
            rule["_source_file"] = yf.name
            idx.inference_rules.append(rule)

        # ── Recycling rules ──────────────────────────────────
        for rule in kb.get("recyclingrules", []):
            rule["_source_file"] = yf.name
            idx.recycling_rules.setdefault(key, []).append(rule)

        # ── Contamination profiles ───────────────────────────
        for prof in kb.get("contaminationprofiles", []):
            prof["_source_file"] = yf.name
            idx.contamination_profiles.setdefault(key, []).append(prof)

        # ── Quality tiers ────────────────────────────────────
        tiers = kb.get("sourcequalitytiers", {})
        if isinstance(tiers, dict) and tiers:
            idx.quality_tiers[key] = tiers

        # ── Product-scrap mapping ────────────────────────────
        psm = kb.get("productscrapmapping", {})
        if isinstance(psm, dict):
            for category, items in psm.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item["_source_file"] = yf.name
                            item["_category"] = category
                            idx.product_scrap_mapping.setdefault(key, []).append(item)

        logger.info(
            "Indexed %s → %s  |  grades=%d  rules=%d  contam=%d",
            yf.name,
            key,
            len(kb.get("materialgrades", [])),
            len([r for r in kb.get("inferencerules", []) if (r.get("inferencetype") or "").lower() not in _SKIP_TYPES]),
            len(kb.get("contaminationprofiles", [])),
        )

    logger.info(
        "KB loaded: %d files, %d polymers, %d grades, %d rules",
        len(idx.files_loaded),
        len(idx.polymers),
        idx.total_grades,
        idx.total_rules,
    )
    return idx

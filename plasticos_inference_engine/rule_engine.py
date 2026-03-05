"""
plasticos_inference/rule_engine.py
Fires premise→conclusion inference rules from the YAML KBs
against an InferenceRequest.
"""

from __future__ import annotations

import logging

from .kb_loader import KBIndex
from .models import (
    InferenceRequest,
    InferenceResult,
    InferenceSource,
    RuleFiring,
)

logger = logging.getLogger("plasticos_inference.rule_engine")


def fire_rules(
    request: InferenceRequest,
    polymer_key: str,
    kb: KBIndex,
) -> tuple[list[InferenceResult], list[RuleFiring]]:
    """
    Evaluate all forward inference rules for the polymer.

    Returns
    -------
    results : list[InferenceResult]
        Inferred values from rules that matched.
    firings : list[RuleFiring]
        Audit trail of which rules fired and why.
    """
    results: list[InferenceResult] = []
    firings: list[RuleFiring] = []

    for rule in kb.inference_rules:
        rule_polymer = rule.get("_polymer", "")
        rule_material = (rule.get("materialtype") or "").upper()

        # Only fire rules for this polymer
        if rule_polymer != polymer_key and rule_material != polymer_key:
            continue

        match = _try_match(rule, request)
        if match is None:
            continue

        rule_id = rule.get("ruleid") or rule.get("inferenceid", "unknown")
        conf = float(rule.get("confidence", 0.70))
        itype = rule.get("inferencetype", "unknown")
        src_file = rule.get("_source_file", "")

        results.append(
            InferenceResult(
                field=match["field"],
                value=match["value"],
                confidence=conf,
                source=InferenceSource.YAML_RULE,
                source_id=rule_id,
                source_file=src_file,
                reasoning=rule.get("reasoning", rule.get("rule", "")),
            )
        )

        firings.append(
            RuleFiring(
                rule_id=rule_id,
                rule_type=itype,
                source_file=src_file,
                confidence=conf,
                field=match["field"],
                value=match["value"],
                reasoning=rule.get("reasoning", ""),
            )
        )

    return results, firings


def _try_match(rule: dict, req: InferenceRequest) -> dict | None:
    """
    Evaluate one rule's premises against the request.
    Returns {"field": str, "value": Any} if matched, else None.
    """
    premise = (rule.get("premise") or rule.get("condition") or "").lower()
    conclusion = rule.get("conclusion", "")
    logic = (rule.get("logic") or "").lower()
    rule_text = (rule.get("rule") or "").lower()
    itype = (rule.get("inferencetype") or "").lower()

    source = (req.source_type or "").lower()
    form = (req.form or "").lower()
    # process reserved for future rule matching
    notes = (req.notes or "").lower()
    app = (req.origin_application or "").lower()

    # ── Property: missing MFI ────────────────────────────────
    if itype == "property" and req.mfi_value is None:
        mfi_keywords = ("melt index", "mfi", "mi ", "melt flow")
        if any(kw in premise for kw in mfi_keywords):
            # Check form alignment
            if form and form in premise:
                return {"field": "mfi_estimate", "value": conclusion}
            if not form:  # no form specified — still fire with lower conf
                return {"field": "mfi_estimate", "value": conclusion}

    # ── Property: missing moisture ───────────────────────────
    if itype == "property" and req.moisture_ppm is None:
        if "moisture" in premise:
            if "outdoor" in notes or "outdoor" in premise:
                return {"field": "moisture_ppm_estimate", "value": conclusion}

    # ── Property: missing contamination ──────────────────────
    if itype == "property" and req.contamination_pct is None:
        if "contamination" in premise:
            if _source_matches(source, premise):
                return {"field": "contamination_pct_estimate", "value": conclusion}

    # ── Quality assessment ───────────────────────────────────
    if itype == "qualityassessment":
        if "color" in logic and req.color:
            return {"field": "quality_note", "value": rule.get("rule", conclusion)}
        if "single" in logic and source in ("pi", "pir", "clean"):
            return {"field": "quality_note", "value": rule.get("rule", conclusion)}

    # ── Processing requirement ───────────────────────────────
    if itype == "processingrequirement":
        if "wash" in logic or "wash" in rule_text:
            if any(kw in app or kw in notes for kw in ("agricultural", "outdoor", "soil")):
                return {"field": "processing_requirement", "value": "washing_required"}
        if "pelletiz" in logic or "pelletiz" in rule_text:
            if form in ("BALES", "REGRIND", "FLAKE", "LOOSE"):
                return {"field": "processing_requirement", "value": "pelletizing_recommended"}

    # ── Contamination assessment ─────────────────────────────
    if itype == "contaminationassessment":
        if req.contamination_pct is not None:
            return {"field": "contamination_note", "value": rule.get("rule", conclusion)}

    # ── Recycling rules (from recyclingrules section) ────────
    if "property retention" in rule_text and source in ("pc", "pcr", "mixed"):
        return {"field": "property_retention_note", "value": rule.get("rule", conclusion)}

    if "food contact" in rule_text and source in ("pc", "pcr"):
        return {"field": "food_contact_restriction", "value": True}

    return None


def _source_matches(source: str, premise: str) -> bool:
    """Check if the source type is mentioned in the premise."""
    source_keywords = {
        "pc": ("post-consumer", "postconsumer", "pcr"),
        "pcr": ("post-consumer", "postconsumer", "pcr"),
        "pi": ("post-industrial", "postindustrial", "pir"),
        "pir": ("post-industrial", "postindustrial", "pir"),
        "mixed": ("mixed",),
        "clean": ("clean", "virgin"),
    }
    keywords = source_keywords.get(source, (source,))
    return any(kw in premise for kw in keywords)

"""
plasticos_inference/engine.py
Main inference engine — the single public entry point.

Usage
-----
    from plasticos_inference import InferenceEngine
    from plasticos_inference.models import InferenceRequest

    engine = InferenceEngine(kb_dir="/path/to/kb")

    # Supplier lead
    resp = engine.infer(InferenceRequest(
        entity_type="supplier", polymer="HDPE", form="BALE", source_type="PC",
    ))

    # Buyer card
    resp = engine.infer(InferenceRequest(
        entity_type="buyer", polymer="PP", process_type="injection molding",
    ))
"""

from __future__ import annotations

import logging
from pathlib import Path

from .contamination_engine import match_contamination
from .grade_engine import infer_from_grades, match_grades
from .kb_loader import KBIndex, load_kb
from .models import (
    InferenceRequest,
    InferenceResponse,
)
from .polymer_aliases import normalize
from .rule_engine import fire_rules
from .tier_engine import classify_tier

logger = logging.getLogger("plasticos_inference")


class InferenceEngine:
    """
    Entity-agnostic polymer inference engine.

    Loads YAML knowledge bases once at init, then serves
    unlimited .infer() calls at zero API cost.
    """

    def __init__(self, kb_dir: Path | str) -> None:
        self.kb: KBIndex = load_kb(kb_dir)
        logger.info(
            "InferenceEngine ready: %d polymers, %d grades, %d rules, %d files",
            len(self.kb.polymers),
            self.kb.total_grades,
            self.kb.total_rules,
            len(self.kb.files_loaded),
        )

    # ── Public API ───────────────────────────────────────────

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        """
        Run all inference engines against a request.
        Works for any entity type (supplier, buyer, intake, material_profile).
        """
        response = InferenceResponse()

        # Normalize polymer
        polymer_key = normalize(request.polymer) if request.polymer else ""
        if not polymer_key or polymer_key not in self.kb.material_grades:
            # Try uppercase as-is
            polymer_key = (request.polymer or "").upper().replace(" ", "_")

        if not polymer_key:
            logger.debug("No polymer provided — skipping inference")
            return response

        # Track which KB files contribute
        consulted: set[str] = set()

        # 1. Grade-based property inference
        grade_results = infer_from_grades(request, polymer_key, self.kb)
        response.results.extend(grade_results)
        response.grade_matches = match_grades(request, polymer_key, self.kb)
        for r in grade_results:
            consulted.add(r.source_file)

        # 2. Rule-based inference
        rule_results, firings = fire_rules(request, polymer_key, self.kb)
        response.results.extend(rule_results)
        response.applicable_rules = firings
        for r in rule_results:
            consulted.add(r.source_file)

        # 3. Quality tier classification
        tier, tier_result = classify_tier(request, polymer_key, self.kb)
        response.quality_tier = tier
        if tier_result:
            response.results.append(tier_result)
            consulted.add(tier_result.source_file)

        # 4. Contamination profile matching
        contam_results = match_contamination(request, polymer_key, self.kb)
        response.results.extend(contam_results)
        for r in contam_results:
            consulted.add(r.source_file)

        # Sort all results by confidence descending
        response.results.sort(key=lambda r: r.confidence, reverse=True)
        response.kb_files_consulted = sorted(f for f in consulted if f)

        logger.info(
            "Inferred %d fields for %s/%s/%s (tier=%s, grades=%d, rules=%d)",
            len(response.results),
            request.entity_type.value if hasattr(request.entity_type, "value") else request.entity_type,
            polymer_key,
            request.form or "*",
            response.quality_tier.value,
            len(response.grade_matches),
            len(response.applicable_rules),
        )

        return response

    # ── Convenience methods ──────────────────────────────────

    @property
    def polymers(self) -> list[str]:
        """List of polymers with loaded knowledge bases."""
        return self.kb.polymers

    @property
    def stats(self) -> dict:
        """Engine statistics."""
        return {
            "polymers": len(self.kb.polymers),
            "total_grades": self.kb.total_grades,
            "total_rules": self.kb.total_rules,
            "files_loaded": self.kb.files_loaded,
        }

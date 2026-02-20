# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Module : classification_engine
# Purpose: Deterministic HOT/COLD classification — zero LLM.
#          Pure Python logic applied after AI normalization.
# ═══════════════════════════════════════════════════════════
"""
Classification Rules (from n8n WebLeadTriage-FIN workflow):

Auto-COLD gates (any one triggers COLD):
  1. Material is PVC
  2. Estimated weight < cold_max_lbs (default 8,000 lbs)
  3. Source is residential / individual / homeowner
  4. Request is a drop-off
  5. Material matches reject list (vinyl siding, appliances, etc.)
  6. Material is not plastic

HOT qualification (all must be true):
  1. Estimated weight >= hot_min_lbs (default 10,000 lbs)
  2. Material IS plastic
  3. Source is commercial or industrial

Everything else → COLD with reasons.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)

# ── Non-plastic keywords ────────────────────────────────────
_NON_PLASTIC_KEYWORDS = frozenset([
    "metal", "steel", "aluminum", "aluminium", "copper", "brass",
    "wood", "lumber", "paper", "cardboard", "glass", "ceramic",
    "concrete", "asphalt", "dirt", "soil", "food waste", "organic",
    "textile", "fabric", "cloth", "rubber tire",
])

# ── Commercial / industrial source indicators ───────────────
_COMMERCIAL_INDICATORS = frozenset([
    "commercial", "industrial", "manufacturing", "factory",
    "warehouse", "distribution", "plant", "facility", "processor",
    "recycler", "broker", "post-industrial", "post_industrial",
    "post-commercial", "post_commercial", "agricultural",
])


@dataclass
class ClassificationResult:
    """Immutable result of the deterministic classification."""

    decision: str  # "hot" or "cold"
    reasons: list[str] = field(default_factory=list)
    cold_gates_triggered: list[str] = field(default_factory=list)
    hot_qualifiers_met: list[str] = field(default_factory=list)


def classify_lead(
    *,
    polymer: str | None,
    material_description: str | None,
    estimated_lbs: int,
    source_description: str | None,
    source_type: str | None,
    reject_materials: frozenset[str],
    reject_sources: frozenset[str],
    hot_min_lbs: int = 10_000,
    cold_max_lbs: int = 8_000,
) -> ClassificationResult:
    """Apply deterministic classification rules.

    All inputs should already be normalized (lowercase, stripped).
    Returns a ClassificationResult with decision and audit trail.
    """
    cold_gates: list[str] = []
    hot_quals: list[str] = []

    mat_lower = (material_description or "").lower().strip()
    src_lower = (source_description or "").lower().strip()
    src_type_lower = (source_type or "").lower().strip()
    poly_lower = (polymer or "").lower().strip()

    # ── COLD Gate 1: PVC ─────────────────────────────────────
    if poly_lower == "pvc":
        cold_gates.append("pvc_material")

    # ── COLD Gate 2: Below minimum weight ────────────────────
    if estimated_lbs < cold_max_lbs:
        cold_gates.append(f"below_{cold_max_lbs}_lbs (est={estimated_lbs})")

    # ── COLD Gate 3: Residential / individual source ─────────
    for pattern in reject_sources:
        if pattern in src_lower or pattern in src_type_lower:
            cold_gates.append(f"rejected_source: {pattern}")
            break

    # ── COLD Gate 4: Reject-list materials ───────────────────
    for pattern in reject_materials:
        if pattern in mat_lower:
            cold_gates.append(f"rejected_material: {pattern}")
            break

    # ── COLD Gate 5: Non-plastic material ────────────────────
    is_plastic = True
    for kw in _NON_PLASTIC_KEYWORDS:
        if kw in mat_lower and not poly_lower:
            is_plastic = False
            cold_gates.append(f"non_plastic: {kw}")
            break

    # ── If any COLD gate triggered → COLD ────────────────────
    if cold_gates:
        return ClassificationResult(
            decision="cold",
            reasons=[f"COLD gate: {g}" for g in cold_gates],
            cold_gates_triggered=cold_gates,
        )

    # ── HOT Qualification ────────────────────────────────────
    # Q1: Weight >= hot_min_lbs
    if estimated_lbs >= hot_min_lbs:
        hot_quals.append(f"weight_gte_{hot_min_lbs}_lbs (est={estimated_lbs})")

    # Q2: Material is plastic
    if is_plastic and poly_lower:
        hot_quals.append(f"is_plastic (polymer={poly_lower})")
    elif is_plastic:
        hot_quals.append("is_plastic (inferred from description)")

    # Q3: Commercial / industrial source
    is_commercial = False
    for indicator in _COMMERCIAL_INDICATORS:
        if indicator in src_lower or indicator in src_type_lower:
            is_commercial = True
            hot_quals.append(f"commercial_source: {indicator}")
            break

    # All three qualifiers must be met for HOT
    if len(hot_quals) >= 3:
        return ClassificationResult(
            decision="hot",
            reasons=[f"HOT qualifier: {q}" for q in hot_quals],
            hot_qualifiers_met=hot_quals,
        )

    # ── Default: COLD (not enough qualifiers) ────────────────
    missing = []
    if estimated_lbs < hot_min_lbs:
        missing.append(f"weight below {hot_min_lbs} lbs")
    if not is_plastic or not poly_lower:
        missing.append("polymer not identified")
    if not is_commercial:
        missing.append("source not commercial/industrial")

    return ClassificationResult(
        decision="cold",
        reasons=[
            f"Insufficient HOT qualifiers ({len(hot_quals)}/3)",
            *[f"Missing: {m}" for m in missing],
        ],
        hot_qualifiers_met=hot_quals,
    )

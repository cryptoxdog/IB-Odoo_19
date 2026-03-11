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
_NON_PLASTIC_KEYWORDS = frozenset(
    [
        "metal",
        "steel",
        "aluminum",
        "aluminium",
        "copper",
        "brass",
        "wood",
        "lumber",
        "paper",
        "cardboard",
        "glass",
        "ceramic",
        "concrete",
        "asphalt",
        "dirt",
        "soil",
        "food waste",
        "organic",
        "textile",
        "fabric",
        "cloth",
        "rubber tire",
    ]
)

# ── Commercial / industrial source indicators ───────────────
_COMMERCIAL_INDICATORS = frozenset(
    [
        "commercial",
        "industrial",
        "manufacturing",
        "factory",
        "warehouse",
        "distribution",
        "plant",
        "facility",
        "processor",
        "recycler",
        "broker",
        "post-industrial",
        "post_industrial",
        "post-commercial",
        "post_commercial",
        "agricultural",
    ]
)


@dataclass
class ClassificationResult:
    """Immutable result of the deterministic classification."""

    decision: str  # "hot" or "cold"
    reasons: list[str] = field(default_factory=list)
    cold_gates_triggered: list[str] = field(default_factory=list)
    hot_qualifiers_met: list[str] = field(default_factory=list)


def _check_cold_gates(
    poly_lower: str,
    mat_lower: str,
    src_lower: str,
    src_type_lower: str,
    estimated_lbs: int,
    reject_materials: frozenset[str],
    reject_sources: frozenset[str],
    cold_max_lbs: int,
) -> tuple[list[str], bool]:
    """Evaluate all COLD gates; return (triggered_gates, is_plastic)."""
    cold_gates: list[str] = []

    if poly_lower == "pvc":
        cold_gates.append("pvc_material")

    if estimated_lbs < cold_max_lbs:
        cold_gates.append(f"below_{cold_max_lbs}_lbs (est={estimated_lbs})")

    for pattern in reject_sources:
        if pattern in src_lower or pattern in src_type_lower:
            cold_gates.append(f"rejected_source: {pattern}")
            break

    for pattern in reject_materials:
        if pattern in mat_lower:
            cold_gates.append(f"rejected_material: {pattern}")
            break

    is_plastic = True
    for kw in _NON_PLASTIC_KEYWORDS:
        if kw in mat_lower and not poly_lower:
            is_plastic = False
            cold_gates.append(f"non_plastic: {kw}")
            break

    return cold_gates, is_plastic


def _check_hot_qualifiers(
    is_plastic: bool,
    poly_lower: str,
    src_lower: str,
    src_type_lower: str,
    estimated_lbs: int,
    hot_min_lbs: int,
) -> tuple[list[str], bool]:
    """Evaluate HOT qualifiers; return (hot_quals, is_commercial)."""
    hot_quals: list[str] = []

    if estimated_lbs >= hot_min_lbs:
        hot_quals.append(f"weight_gte_{hot_min_lbs}_lbs (est={estimated_lbs})")

    if is_plastic and poly_lower:
        hot_quals.append(f"is_plastic (polymer={poly_lower})")
    elif is_plastic:
        hot_quals.append("is_plastic (inferred from description)")

    is_commercial = False
    for indicator in _COMMERCIAL_INDICATORS:
        if indicator in src_lower or indicator in src_type_lower:
            is_commercial = True
            hot_quals.append(f"commercial_source: {indicator}")
            break

    return hot_quals, is_commercial


def _build_insufficient_cold_result(
    hot_quals: list[str],
    is_plastic: bool,
    poly_lower: str,
    is_commercial: bool,
    hot_min_lbs: int,
    estimated_lbs: int,
) -> ClassificationResult:
    """Build the COLD result when insufficient HOT qualifiers are met."""
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
    mat_lower = (material_description or "").lower().strip()
    src_lower = (source_description or "").lower().strip()
    src_type_lower = (source_type or "").lower().strip()
    poly_lower = (polymer or "").lower().strip()

    cold_gates, is_plastic = _check_cold_gates(
        poly_lower,
        mat_lower,
        src_lower,
        src_type_lower,
        estimated_lbs,
        reject_materials,
        reject_sources,
        cold_max_lbs,
    )

    if cold_gates:
        return ClassificationResult(
            decision="cold",
            reasons=[f"COLD gate: {g}" for g in cold_gates],
            cold_gates_triggered=cold_gates,
        )

    hot_quals, is_commercial = _check_hot_qualifiers(
        is_plastic,
        poly_lower,
        src_lower,
        src_type_lower,
        estimated_lbs,
        hot_min_lbs,
    )

    if len(hot_quals) >= 3:
        return ClassificationResult(
            decision="hot",
            reasons=[f"HOT qualifier: {q}" for q in hot_quals],
            hot_qualifiers_met=hot_quals,
        )

    return _build_insufficient_cold_result(
        hot_quals,
        is_plastic,
        poly_lower,
        is_commercial,
        hot_min_lbs,
        estimated_lbs,
    )

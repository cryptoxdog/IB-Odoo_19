# ═══════════════════════════════════════════════════════════════════════════════
# classification_engine.py
# Module : plasticos_web_leads
# Purpose: Deterministic HOT / COLD / WARM classification of normalised leads.
#
# FIXES APPLIED:
# CE-01 — reject list checks are case-insensitive substring matches
# CE-02 — is_plastic=None is UNKNOWN, not False; does NOT trigger cold gate
# CE-03 — is_plastic=True alone is NOT a HOT qualifier (needs polymer or source)
# CE-04 — commercial keyword detection uses word-boundary regex (no substring FP)
# CE-05 — 0-lbs leads get weight:unknown gate, not weight:below_cold_floor gate
# CE-06 — HOT requires ≥ 2 independent qualifiers
# CE-07 — ClassificationResult carries weight_source field
# CE-08 — cold_gates_triggered is a structured list, not free text
# CE-09 — is_commercial=None reduces effective HOT threshold to 80%
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Default reject lists (overridable via classify_lead kwargs)
# ─────────────────────────────────────────────────────────────────────────────
_REJECT_MATERIALS_DEFAULT: list[str] = [
    "metal", "aluminum", "aluminium", "steel", "copper", "iron",
    "glass", "wood", "paper", "cardboard", "rubber", "textile",
    "fabric", "ceramic", "concrete", "asphalt",
]

_REJECT_SOURCES_DEFAULT: list[str] = [
    "household", "residential", "home owner", "homeowner",
    "drop off", "drop-off", "dropoff", "garage sale",
    "dispose", "get rid", "personal use", "consumer drop",
]

# Commercial source keywords — word-boundary protected (FIX CE-04)
_COMMERCIAL_KEYWORDS: list[str] = [
    r"\bmanufactur\w*\b",
    r"\bfacility\b", r"\bfacilities\b",
    r"\bplant\b",          # word-boundary prevents "transplant"
    r"\bwarehouse\b",
    r"\bproduction\b",
    r"\bindustrial\b",
    r"\bprocessor\b",
    r"\brecycler\b",
    r"\bdistributor\b",
    r"\bscrap\s+yard\b",
    r"\bmolder\b", r"\bextruder\b",
    r"\bcompound\w*\b",
]
_COMMERCIAL_PATTERN = re.compile(
    "|".join(_COMMERCIAL_KEYWORDS), re.IGNORECASE
)

# Minimum qualifiers to reach HOT (FIX CE-06)
_MIN_HOT_QUALIFIERS = 2

# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """
    Full audit record of a lead classification decision.

    Attributes:
      decision              : "hot" | "cold"
      reasons               : human-readable list of decision drivers
      cold_gates_triggered  : machine-readable gate IDs that fired COLD
      hot_qualifiers_met    : machine-readable qualifier IDs that fired HOT
      weight_source         : source tag from parse_weight_lbs (FIX CE-07)
      is_plastic            : the is_plastic value used (None = unknown)
      is_commercial_source  : the commercial hint value used
      estimated_lbs         : the weight value used
      effective_hot_min_lbs : the actual threshold applied (accounts for CE-09)
    """
    decision: str
    reasons: list[str] = field(default_factory=list)
    cold_gates_triggered: list[str] = field(default_factory=list)
    hot_qualifiers_met: list[str] = field(default_factory=list)
    weight_source: str = "none"
    is_plastic: Optional[bool] = None
    is_commercial_source: Optional[bool] = None
    estimated_lbs: float = 0.0
    effective_hot_min_lbs: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Main classifier
# ─────────────────────────────────────────────────────────────────────────────

def classify_lead(
    *,
    polymer: Optional[str] = None,
    material_description: Optional[str] = None,
    estimated_lbs: float = 0.0,
    source_description: Optional[str] = None,
    source_type: Optional[str] = None,
    is_plastic_hint: Optional[bool] = None,
    is_commercial_hint: Optional[bool] = None,
    weight_source: str = "none",
    hot_min_lbs: float = 10_000.0,
    cold_max_lbs: float = 8_000.0,
    reject_materials: Optional[list[str]] = None,
    reject_sources: Optional[list[str]] = None,
) -> ClassificationResult:
    """
    Classify a normalised lead as "hot" or "cold".

    HOT requires ALL of:
      1. No COLD gate has fired
      2. Weight ≥ effective_hot_min_lbs (adjusted down 20% if commercial is unknown)
      3. ≥ _MIN_HOT_QUALIFIERS independent positive signals

    COLD fires on the FIRST matching gate (evaluated in priority order).
    """
    reasons: list[str] = []
    cold_gates: list[str] = []
    hot_quals: list[str] = []

    # Normalise inputs
    poly_lower = (polymer or "").strip().lower()
    mat_lower = (material_description or "").strip().lower()
    src_lower = (source_description or "").strip().lower()
    stype_lower = (source_type or "").strip().lower()

    rej_mats = [m.lower() for m in (reject_materials if reject_materials is not None
                                    else _REJECT_MATERIALS_DEFAULT)]
    rej_srcs = [s.lower() for s in (reject_sources if reject_sources is not None
                                    else _REJECT_SOURCES_DEFAULT)]

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 1 — AI explicitly says not plastic (FIX CE-02)
    #   is_plastic=False → cold
    #   is_plastic=None  → unknown, do NOT cold here
    #   is_plastic=True  → pass through to qualifiers
    # ─────────────────────────────────────────────────────────────────────────
    if is_plastic_hint is False:
        cold_gates.append("is_plastic:false")
        reasons.append("AI determined material is not plastic.")

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 2 — AI explicitly says not a commercial source
    # ─────────────────────────────────────────────────────────────────────────
    if is_commercial_hint is False:
        cold_gates.append("is_commercial_source:false")
        reasons.append("AI determined source is not commercial (residential/personal).")

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 3 — Rejected material type (FIX CE-01: case-insensitive)
    # ─────────────────────────────────────────────────────────────────────────
    search_text_mat = f"{poly_lower} {mat_lower}"
    for reject_kw in rej_mats:
        if reject_kw and reject_kw in search_text_mat:
            cold_gates.append("reject_material")
            reasons.append(f"Material contains rejected keyword: '{reject_kw}'.")
            break

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 4 — Rejected source type (FIX CE-01: case-insensitive)
    # ─────────────────────────────────────────────────────────────────────────
    search_text_src = f"{src_lower} {stype_lower}"
    for reject_kw in rej_srcs:
        if reject_kw and reject_kw in search_text_src:
            cold_gates.append("reject_source")
            reasons.append(f"Source contains rejected keyword: '{reject_kw}'.")
            break

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 5 — Weight unknown (FIX CE-05: distinct from below-floor gate)
    # ─────────────────────────────────────────────────────────────────────────
    if estimated_lbs == 0 or weight_source == "none":
        cold_gates.append("weight:unknown")
        reasons.append("No usable weight information — cannot qualify as HOT.")

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 6 — Weight below cold floor (only fires if weight IS known)
    # ─────────────────────────────────────────────────────────────────────────
    elif 0 < estimated_lbs < cold_max_lbs:
        cold_gates.append("weight:below_cold_floor")
        reasons.append(
            f"Weight {estimated_lbs:,.0f} lbs is below COLD floor "
            f"({cold_max_lbs:,.0f} lbs)."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # If any COLD gate fired → return COLD immediately
    # ─────────────────────────────────────────────────────────────────────────
    if cold_gates:
        return ClassificationResult(
            decision="cold",
            reasons=reasons,
            cold_gates_triggered=cold_gates,
            weight_source=weight_source,
            is_plastic=is_plastic_hint,
            is_commercial_source=is_commercial_hint,
            estimated_lbs=estimated_lbs,
            effective_hot_min_lbs=hot_min_lbs,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HOT threshold adjustment (FIX CE-09)
    # If commercial status is unknown, require only 80% of hot_min_lbs.
    # ─────────────────────────────────────────────────────────────────────────
    if is_commercial_hint is None:
        effective_hot_min = hot_min_lbs * 0.80
        reasons.append(
            f"Commercial source unknown — effective HOT threshold reduced to "
            f"{effective_hot_min:,.0f} lbs (80% of {hot_min_lbs:,.0f})."
        )
    else:
        effective_hot_min = hot_min_lbs

    # ─────────────────────────────────────────────────────────────────────────
    # Weight gate: must clear HOT threshold
    # ─────────────────────────────────────────────────────────────────────────
    if estimated_lbs < effective_hot_min:
        reasons.append(
            f"Weight {estimated_lbs:,.0f} lbs is in warm zone (below HOT "
            f"threshold of {effective_hot_min:,.0f} lbs)."
        )
        return ClassificationResult(
            decision="cold",
            reasons=reasons,
            cold_gates_triggered=["weight:below_hot_threshold"],
            weight_source=weight_source,
            is_plastic=is_plastic_hint,
            is_commercial_source=is_commercial_hint,
            estimated_lbs=estimated_lbs,
            effective_hot_min_lbs=effective_hot_min,
        )

    # Weight passes — add qualifier
    hot_quals.append(f"weight:{weight_source}:{estimated_lbs:,.0f}lbs")
    reasons.append(
        f"Weight {estimated_lbs:,.0f} lbs ≥ HOT threshold "
        f"{effective_hot_min:,.0f} lbs."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # HOT QUALIFIER — confirmed polymer
    # ─────────────────────────────────────────────────────────────────────────
    if polymer and poly_lower:
        hot_quals.append(f"polymer_confirmed:{poly_lower}")
        reasons.append(f"Polymer identified: {polymer}.")

    # ─────────────────────────────────────────────────────────────────────────
    # HOT QUALIFIER — commercial source (FIX CE-04: word-boundary regex)
    # ─────────────────────────────────────────────────────────────────────────
    if is_commercial_hint is True:
        hot_quals.append("is_commercial_source:true")
        reasons.append("AI confirmed commercial/industrial source.")
    elif is_commercial_hint is None:
        combined = f"{src_lower} {mat_lower}"
        if _COMMERCIAL_PATTERN.search(combined):
            hot_quals.append("commercial_keyword_detected")
            reasons.append("Commercial keyword detected in source/material description.")

    # ─────────────────────────────────────────────────────────────────────────
    # HOT QUALIFIER — post-industrial source type
    # ─────────────────────────────────────────────────────────────────────────
    if stype_lower in ("post_industrial", "post-industrial"):
        hot_quals.append("source_type:post_industrial")
        reasons.append("Source type is post-industrial.")

    # NOTE: is_plastic=True alone is NOT a HOT qualifier (FIX CE-03)
    # It only confirms material type; commercial viability needs more evidence.

    # ─────────────────────────────────────────────────────────────────────────
    # Decision: HOT requires ≥ _MIN_HOT_QUALIFIERS independent signals (CE-06)
    # ─────────────────────────────────────────────────────────────────────────
    if len(hot_quals) >= _MIN_HOT_QUALIFIERS:
        return ClassificationResult(
            decision="hot",
            reasons=reasons,
            cold_gates_triggered=[],
            hot_qualifiers_met=hot_quals,
            weight_source=weight_source,
            is_plastic=is_plastic_hint,
            is_commercial_source=is_commercial_hint,
            estimated_lbs=estimated_lbs,
            effective_hot_min_lbs=effective_hot_min,
        )

    # Passed weight gate but insufficient qualifiers
    reasons.append(
        f"Insufficient HOT qualifiers: {len(hot_quals)} of {_MIN_HOT_QUALIFIERS} required. "
        f"Qualifiers met: {hot_quals or ['none']}."
    )
    return ClassificationResult(
        decision="cold",
        reasons=reasons,
        cold_gates_triggered=["insufficient_qualifiers"],
        hot_qualifiers_met=hot_quals,
        weight_source=weight_source,
        is_plastic=is_plastic_hint,
        is_commercial_source=is_commercial_hint,
        estimated_lbs=estimated_lbs,
        effective_hot_min_lbs=effective_hot_min,
    )

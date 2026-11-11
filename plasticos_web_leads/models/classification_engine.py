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
# CE-09 — unknown commercial status never reduces a deterministic threshold
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from .evidence_keys import ASSESSMENT_STATUS_ASSESSED
from .evidence_reconciler import polymers_named
from .triage_helpers import WEIGHT_SOURCE_AREA

# ─────────────────────────────────────────────────────────────────────────────
# Default reject lists (overridable via classify_lead kwargs)
# ─────────────────────────────────────────────────────────────────────────────
_REJECT_MATERIALS_DEFAULT: list[str] = [
    "metal",
    "aluminum",
    "aluminium",
    "steel",
    "copper",
    "iron",
    "glass",
    "wood",
    "paper",
    "cardboard",
    "rubber",
    "textile",
    "fabric",
    "ceramic",
    "concrete",
    "asphalt",
]

_REJECT_SOURCES_DEFAULT: list[str] = [
    "household",
    "residential",
    "home owner",
    "homeowner",
    "drop off",
    "drop-off",
    "dropoff",
    "garage sale",
    "dispose",
    "get rid",
    "personal use",
    "consumer drop",
]

# Commercial source keywords — word-boundary protected (FIX CE-04)
_COMMERCIAL_KEYWORDS: list[str] = [
    r"\bmanufactur\w*\b",
    r"\bfacility\b",
    r"\bfacilities\b",
    r"\bplant\b",  # word-boundary prevents "transplant"
    r"\bwarehouse\b",
    r"\bproduction\b",
    r"\bindustrial\b",
    r"\bprocessor\b",
    r"\brecycler\b",
    r"\bdistributor\b",
    r"\bscrap\s+yard\b",
    r"\bmolder\b",
    r"\bextruder\b",
    r"\bcompound\w*\b",
]
_COMMERCIAL_PATTERN = re.compile("|".join(_COMMERCIAL_KEYWORDS), re.IGNORECASE)

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
      effective_hot_min_lbs : the actual threshold applied by deterministic policy
      review_required       : whether a broker must resolve uncertainty before commercial work
      review_reasons        : broker-visible uncertainty cues
      vision_evidence       : deep copy of every successful photo analysis, in photo order
    """

    decision: str
    reasons: list[str] = field(default_factory=list)
    cold_gates_triggered: list[str] = field(default_factory=list)
    hot_qualifiers_met: list[str] = field(default_factory=list)
    weight_source: str = "none"
    is_plastic: bool | None = None
    is_commercial_source: bool | None = None
    estimated_lbs: float = 0.0
    effective_hot_min_lbs: float = 0.0
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    vision_evidence: list[dict] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Main classifier
# ─────────────────────────────────────────────────────────────────────────────


def _successful_vision_evidence(items: list[dict] | None) -> list[dict]:
    """Copy each successful analysis. An error wrapper is not a model emission."""
    copied: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict) or "error" in item:
            continue
        copied.append(copy.deepcopy(item))
    return copied


def _agreed_polymer_hint(evidence: list[dict]) -> str:
    """Return the polymer when every photo that names one names the same one."""
    hints = [
        str(item.get("observed_polymer_hint")).strip()
        for item in evidence
        if isinstance(item.get("observed_polymer_hint"), str) and str(item.get("observed_polymer_hint")).strip()
    ]
    if not hints:
        return ""
    if any(hint.lower() != hints[0].lower() for hint in hints):
        return ""
    return hints[0]


def classify_lead(
    *,
    polymer: str | None = None,
    material_description: str | None = None,
    estimated_lbs: float = 0.0,
    source_description: str | None = None,
    source_type: str | None = None,
    is_plastic_hint: bool | None = None,
    is_commercial_hint: bool | None = None,
    weight_source: str = "none",
    hot_min_lbs: float = 10_000.0,
    cold_max_lbs: float = 8_000.0,
    reject_materials: list[str] | None = None,
    reject_sources: list[str] | None = None,
    economic_eligible: bool | None = None,
    economic_policy_reasons: list[str] | None = None,
    vision_evidence: list[dict] | None = None,
) -> ClassificationResult:
    """
    Classify a normalised lead as "hot" or "cold".

    HOT requires ALL of:
      1. No COLD gate has fired
      2. Weight ≥ effective_hot_min_lbs from an explicit material-class policy
      3. ≥ _MIN_HOT_QUALIFIERS independent positive signals

    COLD fires on the FIRST matching gate (evaluated in priority order).
    """
    reasons: list[str] = []
    cold_gates: list[str] = []
    hot_quals: list[str] = []
    vision_copy = _successful_vision_evidence(vision_evidence)

    # Normalise inputs
    poly_lower = (polymer or "").strip().lower()
    mat_lower = (material_description or "").strip().lower()
    src_lower = (source_description or "").strip().lower()
    stype_lower = (source_type or "").strip().lower()

    rej_mats = [m.lower() for m in (reject_materials if reject_materials is not None else _REJECT_MATERIALS_DEFAULT)]
    rej_srcs = [s.lower() for s in (reject_sources if reject_sources is not None else _REJECT_SOURCES_DEFAULT)]

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
        if reject_kw and re.search(r"\b" + re.escape(reject_kw) + r"\b", search_text_mat):
            cold_gates.append("reject_material")
            reasons.append(f"Material contains rejected keyword: '{reject_kw}'.")
            break

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 4 — Rejected source type (CE-01: case-insensitive word-boundary)
    # ─────────────────────────────────────────────────────────────────────────
    search_text_src = f"{src_lower} {stype_lower}"
    for reject_kw in rej_srcs:
        if reject_kw and re.search(r"\b" + re.escape(reject_kw) + r"\b", search_text_src):
            cold_gates.append("reject_source")
            reasons.append(f"Source contains rejected keyword: '{reject_kw}'.")
            break

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 5 — Weight unknown. A positive pound figure is usable even when
    # the source tag was omitted. Area text is never a pound figure.
    # ─────────────────────────────────────────────────────────────────────────
    if weight_source == WEIGHT_SOURCE_AREA or estimated_lbs <= 0:
        cold_gates.append("weight:unknown")
        reasons.append("No usable weight information — cannot qualify as HOT.")

    # ─────────────────────────────────────────────────────────────────────────
    # COLD GATE 6 — Weight below cold floor (only fires if weight IS known)
    # ─────────────────────────────────────────────────────────────────────────
    elif 0 < estimated_lbs < cold_max_lbs:
        cold_gates.append("weight:below_cold_floor")
        reasons.append(f"Weight {estimated_lbs:,.0f} lbs is below COLD floor ({cold_max_lbs:,.0f} lbs).")

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
            vision_evidence=vision_copy,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HOT threshold is selected by upstream deterministic material-class policy.
    # Unknown commercial status is a broker-review concern, never a threshold
    # discount. Degraded LLM evidence must not inflate HOT volume.
    # ─────────────────────────────────────────────────────────────────────────
    effective_hot_min = hot_min_lbs

    # ─────────────────────────────────────────────────────────────────────────
    # Weight gate: must clear HOT threshold
    # ─────────────────────────────────────────────────────────────────────────
    if estimated_lbs < effective_hot_min:
        reasons.append(
            f"Weight {estimated_lbs:,.0f} lbs is in warm zone (below HOT threshold of {effective_hot_min:,.0f} lbs)."
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
            vision_evidence=vision_copy,
        )

    # Weight passes — add qualifier
    hot_quals.append(f"weight:{weight_source}:{estimated_lbs:,.0f}lbs")
    reasons.append(f"Weight {estimated_lbs:,.0f} lbs ≥ HOT threshold {effective_hot_min:,.0f} lbs.")

    if economic_eligible:
        hot_quals.append("economic_policy:eligible")
        for policy_reason in economic_policy_reasons or []:
            reasons.append(f"Economic policy: {policy_reason}.")

    # ─────────────────────────────────────────────────────────────────────────
    # HOT QUALIFIER — confirmed polymer
    # ─────────────────────────────────────────────────────────────────────────
    # Seller or text polymer wins. An agreed vision hint is used only when text is empty.
    # Quantity, containment, and cleanliness on the photos do not open a cold gate.
    qualifier_polymer = (polymer or "").strip() or _agreed_polymer_hint(vision_copy)
    if qualifier_polymer:
        hot_quals.append(f"polymer_confirmed:{qualifier_polymer.lower()}")
        reasons.append(f"Polymer identified: {qualifier_polymer}.")

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
        review_reasons = []
        if is_commercial_hint is None:
            review_reasons.append("Commercial source evidence is unknown; verify business origin before matching.")
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
            review_required=bool(review_reasons),
            review_reasons=review_reasons,
            vision_evidence=vision_copy,
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
        vision_evidence=vision_copy,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Commercial qualification (ADR-016 2026-11-11 amendment)
#
# The economic LLM recommends HOT / REVIEW / COLD. Everything below is the
# deterministic layer around that recommendation: it names the evidence the
# model may cite, detects the few genuine hard exclusions, and validates the
# recommendation before it controls routing. Keyword lists, thresholds, and
# missing facts are signals here, never a COLD decision by themselves.
# ═══════════════════════════════════════════════════════════════════════════════

QUALIFICATION_SCHEMA_VERSION = "web-lead-qualification/v1"
KEY_QUAL_SCHEMA = "schema_version"

DISPOSITION_HOT = "hot"
DISPOSITION_REVIEW = "review"
DISPOSITION_COLD = "cold"
DISPOSITIONS = (DISPOSITION_HOT, DISPOSITION_REVIEW, DISPOSITION_COLD)

# Who controls routing. legacy: the HOT/COLD classifier, model comments after it.
# shadow: the classifier routes; the validated qualification is recorded beside it.
# live: the validated qualification routes HOT / REVIEW / COLD.
QUALIFICATION_MODE_LEGACY = "legacy"
QUALIFICATION_MODE_SHADOW = "shadow"
QUALIFICATION_MODE_LIVE = "live"
QUALIFICATION_MODES = (QUALIFICATION_MODE_LEGACY, QUALIFICATION_MODE_SHADOW, QUALIFICATION_MODE_LIVE)

MASS_BASIS_SELLER_STATED = "seller_stated"
MASS_BASIS_CALCULATED = "calculated"
MASS_BASIS_INFERRED = "inferred"
MASS_BASIS_UNKNOWN = "unknown"
# A HOT intake may carry a seller-stated mass, or one calculated from a seller
# unit count with a disclosed unit weight. A model-inferred mass is not enough.
_INTAKE_MASS_BASES = frozenset({MASS_BASIS_SELLER_STATED, MASS_BASIS_CALCULATED})

# Below this text-model confidence, a negative fact is uncertain, not evidence.
_NEGATIVE_FACT_MIN_CONFIDENCE = 0.6
# Below this vision confidence, a polymer hint cannot confirm the polymer alone.
_VISION_POLYMER_MIN_CONFIDENCE = 0.7
# A COLD recommendation below this confidence goes to a human.
_COLD_MIN_CONFIDENCE = 0.6

_PLASTIC_TERMS = re.compile(
    r"\b(?:plastics?|resins?|poly\w*|hdpe|ldpe|lldpe|pp|pet|rpet|ps|hips|eps|pvc|abs|nylon|pa\d*|pc|pbt|pom|"
    r"acetal|pmma|acrylic|ppo|tpe|tpo|tpu|tpv|eva|pla|bopp|vinyl|frp|fiberglass[- ]reinforced)\b",
    re.IGNORECASE,
)

MATERIAL_SUPPORTED = "supported"
MATERIAL_UNCERTAIN = "uncertain"
MATERIAL_UNSUITABLE = "unsuitable"
SIGNAL_STRONG = "strong"
_SELLER_STATED_SOURCES = frozenset({"weight_per_load_field_lbs", "range_lbs"})

QUALIFICATION_REF_PREFIXES = ("seller.", "quantity.", "ai.", "vision.", "conflict.", "policy.", "risk.")


def mass_basis(weight_source: str | None, lbs: float | None) -> str:
    """Name how a per-load pound figure was obtained. Unknown mass stays unknown."""
    source = (weight_source or "").strip()
    if not lbs or lbs <= 0 or source in ("", "none", WEIGHT_SOURCE_AREA):
        return MASS_BASIS_UNKNOWN
    if source.startswith("explicit_") or source in _SELLER_STATED_SOURCES:
        return MASS_BASIS_SELLER_STATED
    if source.startswith(("unit_count:", "pallet_count", "bare_number:")):
        # A seller count or bare number converted with a disclosed unit assumption.
        return MASS_BASIS_CALCULATED
    return MASS_BASIS_INFERRED


def _keyword_hits(text: str, keywords) -> list[str]:
    lowered = (text or "").lower()
    hits = []
    for keyword in keywords or ():
        keyword = (keyword or "").strip().lower()
        if keyword and re.search(r"\b" + re.escape(keyword) + r"\b", lowered) and keyword not in hits:
            hits.append(keyword)
    return hits


def detect_risk_indicators(
    *,
    polymer: str | None,
    material_text: str | None,
    source_text: str | None,
    reject_materials=None,
    reject_sources=None,
) -> list[str]:
    """Operator reject terms as risk indicators. A hit is evidence to weigh, not a decision."""
    material_keywords = reject_materials if reject_materials else _REJECT_MATERIALS_DEFAULT
    source_keywords = reject_sources if reject_sources else _REJECT_SOURCES_DEFAULT
    indicators = [
        f"material_keyword:{hit}" for hit in _keyword_hits(f"{polymer or ''} {material_text or ''}", material_keywords)
    ]
    indicators.extend(f"source_keyword:{hit}" for hit in _keyword_hits(source_text or "", source_keywords))
    return indicators


def detect_hard_exclusions(
    *,
    polymer: str | None,
    material_text: str | None,
    is_plastic_hint: bool | None,
    reject_materials=None,
) -> list[str]:
    """Return the deterministic exclusions that make a submission clearly unsuitable.

    Only a nonplastic-only offer qualifies: the seller's own material words name
    a nonplastic material, name no plastic at all, and the text model did not
    find plastic. A composite such as fiberglass-reinforced plastic, or a
    seller who names a polymer beside a nonplastic word, is not excluded.
    """
    text = f"{polymer or ''} {material_text or ''}".strip()
    if not text or is_plastic_hint is True or _PLASTIC_TERMS.search(text):
        return []
    material_keywords = reject_materials if reject_materials else _REJECT_MATERIALS_DEFAULT
    hits = _keyword_hits(text, material_keywords)
    if not hits:
        return []
    return [f"nonplastic_only:{hits[0]}"]


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _agreed_confident_polymer(vision: list[dict]) -> str:
    confident = [
        item
        for item in vision
        if isinstance(item, dict) and float(item.get("confidence") or 0.0) >= _VISION_POLYMER_MIN_CONFIDENCE
    ]
    return _agreed_polymer_hint(confident)


def build_qualification_signals(
    *,
    seller: dict | None,
    merged: dict | None,
    quantity: dict | None,
    vision: list[dict] | None,
    conflicts: list[dict] | None,
    clarification_requests: list[str] | None,
    economic_eligibility: dict | None,
    risk_indicators: list[str] | None,
    hard_exclusions: list[str] | None,
    cold_max_lbs: float,
) -> dict:
    """Build the evidence dimensions and the closed set of evidence references.

    ``evidence_refs`` is the only vocabulary the commercial model may cite. A
    reference exists only when its fact is present, so a citation always
    points at evidence that was actually supplied.
    """
    seller = dict(seller or {})
    merged = dict(merged or {})
    quantity = dict(quantity or {})
    vision_rows = [dict(item) for item in (vision or []) if isinstance(item, dict) and "error" not in item]
    conflicts = [dict(item) for item in (conflicts or []) if isinstance(item, dict)]
    refs: dict[str, object] = {}

    for key in (
        "material_description",
        "material_composition_text",
        "quantity_text",
        "weight_per_load_text",
        "frequency_text",
        "source_description",
        "contaminants_text",
        "company_name",
        "pickup_location_text",
        "pickup_postal_code",
    ):
        if _present(seller.get(key)):
            refs[f"seller.{key}"] = str(seller.get(key))[:500]

    lbs = float(merged.get("estimated_lbs") or 0)
    basis = mass_basis(merged.get("lbs_source"), lbs)
    if lbs > 0:
        refs["quantity.load_weight_lbs"] = dict(lbs=lbs, basis=basis, source=merged.get("lbs_source"))
    if _present(quantity.get("loads_per_month")):
        refs["quantity.loads_per_month"] = quantity.get("loads_per_month")
    if _present(quantity.get("cadence_period")):
        refs["quantity.cadence"] = {
            "count": quantity.get("cadence_count_low"),
            "period": quantity.get("cadence_period"),
        }
    if _present(quantity.get("current_inventory_count_low")):
        refs["quantity.current_inventory"] = {
            "count": quantity.get("current_inventory_count_low"),
            "unit": quantity.get("current_inventory_unit"),
        }
    supply_mode = quantity.get("supply_mode") or merged.get("frequency") or ""
    if supply_mode and supply_mode != "unclear":
        refs["quantity.supply_mode"] = supply_mode

    polymer = (merged.get("polymer") or "").strip()
    for key in ("polymer", "form", "material_grade", "source_type", "is_plastic", "is_commercial_source", "color"):
        if _present(merged.get(key)):
            refs[f"ai.{key}"] = merged.get(key)
    for index, item in enumerate(vision_rows):
        refs[f"vision.{index}"] = {
            key: item.get(key)
            for key in (
                "observed_form",
                "observed_color",
                "observed_polymer_hint",
                "contamination_visible",
                "contamination_notes",
                "packaging",
                "visual_summary",
                "confidence",
            )
            if _present(item.get(key))
        }
    for item in conflicts:
        refs[f"conflict.{item.get('field', 'unknown')}"] = item
    if economic_eligibility:
        refs["policy.economic_eligibility"] = dict(economic_eligibility)
    for indicator in list(risk_indicators or []) + list(hard_exclusions or []):
        refs[f"risk.{indicator}"] = indicator

    vision_polymer = _agreed_confident_polymer(vision_rows)
    # The seller's own words naming exactly one polymer are supported evidence.
    seller_polymers = sorted(
        polymers_named(
            " ".join(str(seller.get(key) or "") for key in ("material_description", "material_composition_text"))
        )
    )
    if hard_exclusions:
        material_status = MATERIAL_UNSUITABLE
    elif polymer or vision_polymer or len(seller_polymers) == 1:
        material_status = MATERIAL_SUPPORTED
    else:
        material_status = MATERIAL_UNCERTAIN

    text_confidence = float(merged.get("confidence") or 0.0)
    negative_facts: list[str] = []
    if merged.get("is_plastic") is False and text_confidence >= _NEGATIVE_FACT_MIN_CONFIDENCE:
        negative_facts.append("ai.is_plastic")
    if merged.get("is_commercial_source") is False and text_confidence >= _NEGATIVE_FACT_MIN_CONFIDENCE:
        negative_facts.append("ai.is_commercial_source")
    if basis in _INTAKE_MASS_BASES and 0 < lbs < cold_max_lbs:
        negative_facts.append("quantity.load_weight_lbs")

    loads_per_month = quantity.get("loads_per_month")
    if loads_per_month is None:
        loads_per_month = merged.get("loads_per_month") or None
    return {
        KEY_QUAL_SCHEMA: QUALIFICATION_SCHEMA_VERSION,
        "material": {
            "status": material_status,
            "polymer_code": polymer or None,
            "vision_polymer": vision_polymer or None,
            "seller_polymers": seller_polymers,
            "form_code": merged.get("form"),
            "material_grade_code": merged.get("material_grade"),
            "contamination_visible": any(item.get("contamination_visible") is True for item in vision_rows),
        },
        "scale": {
            "load_weight_lbs": lbs or None,
            "load_weight_lbs_high": merged.get("estimated_lbs_high") or None,
            "mass_basis": basis,
            "loads_per_month": loads_per_month,
            "supply_mode": supply_mode or "unclear",
            "recurring": supply_mode == "ongoing" or bool(loads_per_month),
            "meets_policy_threshold": bool((economic_eligibility or {}).get("eligible")),
            "below_cold_floor": "quantity.load_weight_lbs" in negative_facts,
        },
        "source": {
            "is_commercial_hint": merged.get("is_commercial_source"),
            "source_type_code": merged.get("source_type"),
            "text_confidence": text_confidence,
        },
        "conflicts": sorted({str(item.get("field", "unknown")) for item in conflicts}),
        "missing_information": sorted(set(clarification_requests or [])),
        "risk_indicators": list(risk_indicators or []),
        "hard_exclusions": list(hard_exclusions or []),
        "negative_facts": negative_facts,
        "evidence_refs": refs,
    }


def derive_final_disposition(
    *,
    assessment_record: dict | None,
    signals: dict,
) -> dict:
    """Validate the model recommendation and return the disposition that routes the lead.

    Order (ADR-016, 2026-11-11 amendment):
      1. No usable assessment  → REVIEW (never a silent COLD, never a HOT).
      2. A hard exclusion      → COLD.
      3. Recommended HOT       → HOT only when every intake fact is valid.
      4. Recommended COLD      → COLD only when negative evidence supports it.
      5. Otherwise             → REVIEW.
    Every difference between the recommendation and the final disposition is
    recorded with its reason.
    """
    record = dict(assessment_record or {})
    assessment = record.get("assessment") if isinstance(record.get("assessment"), dict) else {}
    recommendation = assessment.get("recommended_disposition")
    if recommendation not in DISPOSITIONS:
        recommendation = None
    supporting = list(assessment.get("supporting_evidence_refs") or [])
    contradictory = list(assessment.get("contradictory_evidence_refs") or [])
    confidence = float(assessment.get("confidence") or 0.0)
    reasons: list[str] = []

    if record.get("status") != ASSESSMENT_STATUS_ASSESSED or recommendation is None:
        final = DISPOSITION_REVIEW
        reasons.append(
            "Commercial qualification is unavailable ("
            + str(record.get("reason") or record.get("status") or "no recommendation")
            + "); a broker must review and the assessment can be retried."
        )
    elif signals.get("hard_exclusions"):
        final = DISPOSITION_COLD
        reasons.append("Hard exclusion: " + ", ".join(signals["hard_exclusions"]) + ".")
    elif recommendation == DISPOSITION_HOT:
        blockers = intake_blockers(signals)
        if assessment.get("material_suitability") == MATERIAL_UNSUITABLE:
            blockers.append("The model judged the material unsuitable while recommending HOT.")
        if not supporting:
            blockers.append("The HOT recommendation cites no supplied evidence.")
        final = DISPOSITION_REVIEW if blockers else DISPOSITION_HOT
        reasons.extend(blockers)
    elif recommendation == DISPOSITION_COLD:
        negative = list(signals.get("negative_facts") or [])
        if assessment.get("material_suitability") == MATERIAL_UNSUITABLE and (supporting or contradictory):
            negative.append("assessment.material_suitability")
        problems = []
        if not (supporting or contradictory):
            problems.append("The COLD recommendation cites no supplied evidence.")
        if not negative:
            problems.append("No direct negative evidence supports COLD; missing facts are not proof of no value.")
        if confidence < _COLD_MIN_CONFIDENCE:
            problems.append(f"COLD confidence {confidence:.2f} is below {_COLD_MIN_CONFIDENCE:.2f}.")
        final = DISPOSITION_REVIEW if problems else DISPOSITION_COLD
        reasons.extend(problems or [f"Negative evidence: {', '.join(negative)}."])
    else:
        final = DISPOSITION_REVIEW
        reasons.append("The model recommended broker review.")

    high_priority = final == DISPOSITION_REVIEW and (
        recommendation == DISPOSITION_HOT or assessment.get("opportunity_signal") == SIGNAL_STRONG
    )
    return {
        KEY_QUAL_SCHEMA: QUALIFICATION_SCHEMA_VERSION,
        "model_recommendation": recommendation,
        "final_disposition": final,
        "overridden": recommendation is not None and recommendation != final,
        "override_reasons": reasons if recommendation is not None and recommendation != final else [],
        "reasons": reasons,
        "review_priority": "high" if high_priority else "normal",
        "intake_ready": not intake_blockers(signals),
        "missing_information": sorted(
            set(signals.get("missing_information") or []) | set(assessment.get("missing_information") or [])
        ),
        "recommended_clarification": list(assessment.get("recommended_clarification") or []),
        "hard_exclusions": list(signals.get("hard_exclusions") or []),
    }


def intake_blockers(signals: dict) -> list[str]:
    """Facts that must be valid before an automatic intake is created. Empty when ready."""
    material = signals.get("material") or {}
    scale = signals.get("scale") or {}
    blockers: list[str] = []
    if scale.get("mass_basis") not in _INTAKE_MASS_BASES or not scale.get("load_weight_lbs"):
        blockers.append(
            "Per-load weight is not stated or calculable from the seller's words; "
            "an intake would need an invented quantity."
        )
    if material.get("status") != MATERIAL_SUPPORTED:
        blockers.append("Material identity is not supported by seller, text, or confident photo evidence.")
    if signals.get("conflicts"):
        blockers.append("Unresolved evidence conflict: " + ", ".join(signals["conflicts"]) + ".")
    return blockers

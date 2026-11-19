"""Deterministic economic eligibility signals for web-lead qualification.

Under ``legacy`` and ``shadow`` qualification the threshold here still feeds the
legacy HOT/COLD classifier. Under ``live`` qualification (ADR-016, 2026-11-11
amendment) the result is an advisory signal handed to the commercial model and
the disposition validator. A known, seller-stated or calculated weight below
the configured cold floor is direct negative evidence the validator may weigh.

An unknown per-load weight is missing evidence. ``evaluate_economic_eligibility``
keeps ``eligible`` false and records ``economic_evidence:weight_unknown``. This
function does not choose a disposition. Unknown weight is not a review
disposition.

``PLANNING_DEFAULTS_V1`` is the single D7 planning object. Seller weight wins.
Its figures are planning references only: they are never written into
``estimated_lbs_per_load`` or ``quantity_per_load_lbs``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_REUSABLE_ITEM_POLICY_CODES = frozenset({"PLASTIC_PALLETS", "PALLETS", "TOTES", "CRATES"})


@dataclass(frozen=True)
class PlanningDefaultsV1:
    """D7 planning figures. Not a stored per-load quantity and not a disposition.

    ``trailers`` names the only planning equipment: one full domestic 53-foot
    trailer. ``stored_per_load_lbs`` returns a seller-stated weight or nothing.
    """

    policy_ref: str = "web-lead-planning-defaults/v1"
    mixed_plastic_pallets_lbs: tuple[int, int] = (10_000, 12_000)
    baled_film_lbs: int = 36_000
    pellets_lbs: int = 40_000
    trailers: tuple[str, ...] = ("full domestic 53-foot trailer",)
    seller_weight_wins: bool = True

    def stored_per_load_lbs(self, seller_lbs: float | None) -> float | None:
        """Pounds that may be stored. Planning figures are never returned."""
        if not self.seller_weight_wins or seller_lbs is None or seller_lbs <= 0:
            return None
        return float(seller_lbs)

    def as_evidence(self) -> dict[str, Any]:
        """JSON values for the evidence bundle. Not a load weight."""
        low, high = self.mixed_plastic_pallets_lbs
        weights: dict[str, Any] = {}
        weights["mixed_plastic_pallets"] = {"low_lb": low, "high_lb": high, "unit": "lb"}
        weights["baled_film"] = {"lb": self.baled_film_lbs, "unit": "lb"}
        weights["pellets"] = {"lb": self.pellets_lbs, "unit": "lb"}
        payload: dict[str, Any] = {}
        payload["policy_ref"] = self.policy_ref
        payload["weights"] = weights
        payload["trailers"] = list(self.trailers)
        return payload


PLANNING_DEFAULTS_V1 = PlanningDefaultsV1()


@dataclass(frozen=True)
class EconomicEligibilityResult:
    """Auditable deterministic result used before non-authoritative LLM assessment."""

    eligible: bool
    opportunity_class: str
    applicable_hot_min_lbs: float
    policy_version: str = "web-lead-economic-policy/v1"
    policy_applied: str = "standard"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "opportunity_class": self.opportunity_class,
            "applicable_hot_min_lbs": self.applicable_hot_min_lbs,
            "policy_version": self.policy_version,
            "policy_applied": self.policy_applied,
            "reasons": list(self.reasons),
        }


def evaluate_economic_eligibility(
    *,
    estimated_lbs: float,
    standard_hot_min_lbs: float,
    reusable_item_hot_min_lbs: float,
    polymer_code: str | None,
    form_code: str | None,
    material_grade_code: str | None = None,
    reusable_item_policy_codes: frozenset[str] | None = None,
) -> EconomicEligibilityResult:
    """Apply the lower threshold only to explicitly approved reusable items.

    A polymer alone, including LDPE film, never activates the lower threshold.
    The reusable-item taxonomy must be declared by a canonical polymer code,
    material form code, or material grade code.  Unknown material identity
    uses the standard policy.
    """
    polymer = (polymer_code or "").strip().upper()
    form = (form_code or "").strip().upper()
    material_grade = (material_grade_code or "").strip().upper()
    allow_list = reusable_item_policy_codes or DEFAULT_REUSABLE_ITEM_POLICY_CODES
    is_reusable_item = polymer in allow_list or form in allow_list or material_grade in allow_list
    threshold = reusable_item_hot_min_lbs if is_reusable_item else standard_hot_min_lbs
    policy_applied = "reusable_item" if is_reusable_item else "standard"
    opportunity_class = "reusable_item" if is_reusable_item else "commodity_material"
    reasons = [f"policy:{policy_applied}", f"threshold:{threshold:,.0f}lbs"]

    if not is_reusable_item and polymer in {"LDPE", "LLDPE"}:
        reasons.append("polymer_only_no_lower_threshold")
    if not estimated_lbs:
        reasons.append("economic_evidence:weight_unknown")
    elif estimated_lbs < threshold:
        reasons.append("economic_evidence:below_policy_threshold")
    else:
        reasons.append("economic_evidence:meets_policy_threshold")

    return EconomicEligibilityResult(
        eligible=estimated_lbs >= threshold > 0,
        opportunity_class=opportunity_class,
        applicable_hot_min_lbs=threshold,
        policy_applied=policy_applied,
        reasons=tuple(reasons),
    )

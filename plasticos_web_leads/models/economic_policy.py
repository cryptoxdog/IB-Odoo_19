"""Deterministic economic eligibility policy for web-lead opportunity routing.

This policy decides whether a lead is eligible to reach broker review.  An LLM
can later explain or assess operational context, but cannot override a hard
commercial, evidence, or quantity gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_REUSABLE_ITEM_POLICY_CODES = frozenset({"PLASTIC_PALLETS", "PALLETS", "TOTES", "CRATES"})


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
    reusable_item_policy_codes: frozenset[str] | None = None,
) -> EconomicEligibilityResult:
    """Apply the lower threshold only to explicitly approved reusable items.

    A polymer alone, including LDPE film, never activates the lower threshold.
    The reusable-item taxonomy must be declared by a canonical polymer code or
    material form code.  Unknown material identity uses the standard policy.
    """
    polymer = (polymer_code or "").strip().upper()
    form = (form_code or "").strip().upper()
    allow_list = reusable_item_policy_codes or DEFAULT_REUSABLE_ITEM_POLICY_CODES
    is_reusable_item = polymer in allow_list or form in allow_list
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

"""
plasticos_inference/tier_engine.py
Classifies source quality into tier 1–4 using YAML tier definitions.
"""

from __future__ import annotations

from .kb_loader import KBIndex
from .models import (
    InferenceRequest,
    InferenceResult,
    InferenceSource,
    QualityTier,
)

# Source type → default tier mapping (before KB override)
_SOURCE_TIER_MAP: dict[str, QualityTier] = {
    "pi": QualityTier.TIER1,
    "pir": QualityTier.TIER1,
    "clean": QualityTier.TIER1,
    "pc": QualityTier.TIER3,  # upgraded to T2 if contamination low
    "pcr": QualityTier.TIER3,
    "mixed": QualityTier.TIER3,
    "cont": QualityTier.TIER3,
    "dirty": QualityTier.TIER4,
    "off": QualityTier.TIER2,
    "reuse": QualityTier.TIER2,
}


def classify_tier(
    request: InferenceRequest,
    polymer_key: str,
    kb: KBIndex,
) -> tuple[QualityTier, InferenceResult | None]:
    """
    Determine the quality tier for a material.

    Logic:
    1. If source_type maps to a base tier, start there.
    2. If contamination_pct is known, adjust up or down.
    3. Cross-reference KB tier definitions for property retention.

    Returns (tier, InferenceResult or None).
    """
    source = (request.source_type or "").upper()
    source_lower = source.lower()
    contam = request.contamination_pct

    # Already provided?
    if request.quality_tier:
        try:
            return QualityTier(request.quality_tier.lower()), None
        except ValueError:
            pass

    # Base tier from source type
    base = _SOURCE_TIER_MAP.get(source_lower)
    if base is None:
        return QualityTier.UNKNOWN, None

    # Contamination-based adjustment
    tier = base
    if contam is not None:
        if contam <= 0.5:
            tier = QualityTier.TIER1
        elif contam <= 3.0:
            tier = QualityTier.TIER2
        elif contam <= 8.0:
            tier = QualityTier.TIER3
        else:
            tier = QualityTier.TIER4
        # Don't upgrade PI/PIR past tier1 regardless
        if base == QualityTier.TIER1 and tier.value > base.value:
            tier = base

    # Build reasoning from KB tier definition
    tiers = kb.quality_tiers.get(polymer_key, {})
    tier_key = tier.value  # e.g. "tier1"
    tier_data = tiers.get(tier_key, tiers.get(f"{tier_key}premium", {}))
    definition = ""
    if isinstance(tier_data, dict):
        definition = tier_data.get("definition", "")[:200]

    result = InferenceResult(
        field="quality_tier",
        value=tier.value,
        confidence=0.80 if contam is not None else 0.65,
        source=InferenceSource.YAML_TIER,
        source_id=tier_key,
        source_file=f"{polymer_key.lower()}_compounding_recycling_v7.0r.yaml",
        reasoning=(f"Source '{source}' + contamination {contam or 'unknown'}% → {tier.value}. " f"{definition}"),
    )
    return tier, result

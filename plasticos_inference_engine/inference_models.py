"""
plasticos_inference/models.py
Typed data contracts for the inference engine.
Entity-agnostic — works for suppliers, buyers, intakes, material profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EntityType(StrEnum):
    """What kind of record is being inferred against."""

    SUPPLIER = "supplier"
    BUYER = "buyer"
    INTAKE = "intake"
    MATERIAL_PROFILE = "material_profile"
    UNKNOWN = "unknown"


class InferenceSource(StrEnum):
    """Where the inferred value came from."""

    YAML_GRADE = "yaml_grade"
    YAML_RULE = "yaml_rule"
    YAML_TIER = "yaml_tier"
    YAML_CONTAMINATION = "yaml_contamination"
    ONTOLOGY = "ontology"
    DEFAULT = "default"


class QualityTier(StrEnum):
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"
    TIER4 = "tier4"
    UNKNOWN = "unknown"


# ── Request ──────────────────────────────────────────────────


@dataclass
class InferenceRequest:
    """
    Input to the inference engine.
    Provide whatever fields you know — the engine fills the gaps.
    """

    entity_type: EntityType | str = EntityType.UNKNOWN

    # Material identity (any that are known)
    polymer: str | None = None
    form: str | None = None
    color: str | None = None
    source_type: str | None = None
    grade_hint: str | None = None

    # Process context
    process_type: str | None = None
    origin_sector: str | None = None
    origin_application: str | None = None

    # Known properties (engine skips inference for fields already filled)
    mfi_value: float | None = None
    density_value: float | None = None
    moisture_ppm: int | None = None
    contamination_pct: float | None = None
    has_metal: bool | None = None
    has_fr: bool | None = None
    filler_type: str | None = None
    filler_pct: float | None = None

    # Quality context
    quality_tier: str | None = None
    quality_tier_required: str | None = None  # buyer-side

    # Volume (for tier plausibility checks)
    monthly_volume_lbs: int | None = None

    # Free text (parsed for clues)
    notes: str | None = None

    def __post_init__(self):
        if isinstance(self.entity_type, str):
            try:
                self.entity_type = EntityType(self.entity_type.lower())
            except ValueError:
                self.entity_type = EntityType.UNKNOWN


# ── Result atoms ─────────────────────────────────────────────


@dataclass
class InferenceResult:
    """One inferred field value."""

    field: str
    value: Any
    confidence: float  # 0.0 – 1.0
    source: InferenceSource
    source_id: str = ""  # rule ID or grade ID
    source_file: str = ""  # originating YAML filename
    reasoning: str = ""


@dataclass
class GradeMatch:
    """A material grade that matches the request context."""

    grade_id: str
    grade_name: str
    polymer: str
    source_file: str
    match_score: float  # 0.0 – 1.0
    properties: dict = field(default_factory=dict)


@dataclass
class RuleFiring:
    """An inference rule that fired."""

    rule_id: str
    rule_type: str
    source_file: str
    confidence: float
    field: str
    value: Any
    reasoning: str


# ── Response ─────────────────────────────────────────────────


@dataclass
class InferenceResponse:
    """Full output from the inference engine."""

    results: list[InferenceResult] = field(default_factory=list)
    quality_tier: QualityTier = QualityTier.UNKNOWN
    grade_matches: list[GradeMatch] = field(default_factory=list)
    applicable_rules: list[RuleFiring] = field(default_factory=list)
    kb_files_consulted: list[str] = field(default_factory=list)

    @property
    def total_inferences(self) -> int:
        return len(self.results)

    @property
    def avg_confidence(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.confidence for r in self.results) / len(self.results)

    def get(self, field_name: str) -> InferenceResult | None:
        """Get the highest-confidence result for a field."""
        hits = [r for r in self.results if r.field == field_name]
        return max(hits, key=lambda r: r.confidence) if hits else None

    def to_dict(self) -> dict:
        """Flat dict of field→value for the best result per field."""
        seen: dict[str, InferenceResult] = {}
        for r in self.results:
            if r.field not in seen or r.confidence > seen[r.field].confidence:
                seen[r.field] = r
        return {k: v.value for k, v in seen.items()}

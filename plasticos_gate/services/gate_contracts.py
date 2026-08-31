"""Typed Odoo client-side contracts for Gate-routed intelligence calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OdooContext:
    model: str
    record_id: int
    company_id: int | None = None
    user_id: int | None = None
    db_name: str | None = None
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "model": self.model,
            "record_id": self.record_id,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "db_name": self.db_name,
            "correlation_id": self.correlation_id,
        }
        return {k: v for k, v in data.items() if v not in (None, "")}


@dataclass(slots=True)
class ConvergeRequest:
    """EIE EnrichRequest-shaped converge request (entity/object_type/objective/max_variations).

    Canonical Odoo identity rides in ``entity["id"]`` — the field EIE resolves
    entity identity from. ``entity["_odoo_entity_id"]`` is dual-populated for one
    migration window only. Identity is never expressed as a Gate-level transform.
    """

    entity: dict[str, Any] = field(default_factory=dict)
    object_type: str = "Account"
    objective: str = "Full entity enrichment and inference"
    max_variations: int = 5
    kb_context: str | None = None
    idempotency_key: str | None = None
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "entity": self.entity,
            "object_type": self.object_type,
            "objective": self.objective,
            "max_variations": self.max_variations,
        }
        if self.kb_context is not None:
            data["kb_context"] = self.kb_context
        if self.idempotency_key is not None:
            data["idempotency_key"] = self.idempotency_key
        if self.odoo:
            data["odoo"] = self.odoo
        return data


@dataclass(slots=True)
class ConvergeResponse:
    """EIE EnrichResponse carried through without field loss or fabrication.

    ``total_cost_usd`` and ``writeback_applied`` are explicitly UNAVAILABLE
    (always None): EnrichResponse has no cost-in-USD or writeback field
    (DNB-006). Cost is ``tokens_used``.
    """

    status: str | None = None
    state: str | None = None
    failure_reason: str | None = None
    final_fields: dict[str, Any] = field(default_factory=dict)
    pass_count: int | None = None
    variation_count: int | None = None
    confidence: float | None = None
    consensus_threshold: float | None = None
    uncertainty_score: float | None = None
    processing_time_ms: int | None = None
    quality_tier: str | None = None
    inference_version: str | None = None
    kb_content_hash: str | None = None
    kb_files_consulted: list[Any] = field(default_factory=list)
    kb_fragment_ids: list[Any] = field(default_factory=list)
    inferences: list[Any] = field(default_factory=list)
    grade_matches: list[Any] = field(default_factory=list)
    enrichment_payload: Any = None
    feature_vector: Any = None
    tokens_used: int | None = None
    total_cost_usd: None = None  # UNAVAILABLE: EIE has no cost-in-USD field (DNB-006)
    writeback_applied: None = None  # UNAVAILABLE: converge performs no writeback (DNB-006)
    raw: dict[str, Any] = field(default_factory=dict)


# ── Canonical Graph match directions ─────────────────────────────
# PlasticOS Graph recognises exactly these two directions. Anything else is
# rejected by the Graph handler, so Odoo must never emit a private spelling.
MATCH_DIRECTION_SUPPLY_TO_BUYER = "supply_opportunity_to_buyer_facility"
MATCH_DIRECTION_BUYER_TO_SUPPLY = "buyer_demand_to_supply_opportunity"

CANONICAL_MATCH_DIRECTIONS = frozenset(
    {
        MATCH_DIRECTION_SUPPLY_TO_BUYER,
        MATCH_DIRECTION_BUYER_TO_SUPPLY,
    }
)

#: Odoo-local legacy spellings mapped onto the canonical Graph direction.
#: ``intake_to_buyer`` was an Odoo-side invention Graph never accepted; it is
#: normalised here for one migration window rather than silently forwarded.
LEGACY_MATCH_DIRECTIONS = {
    "intake_to_buyer": MATCH_DIRECTION_SUPPLY_TO_BUYER,
    "buyer_to_intake": MATCH_DIRECTION_BUYER_TO_SUPPLY,
}


def normalize_match_direction(direction: str | None) -> str:
    """Return the canonical Graph match direction for ``direction``.

    Canonical values pass through. Known legacy Odoo spellings are translated.
    Anything else raises: an unknown direction must fail closed here rather than
    reach Graph, which rejects it after a full round trip.
    """
    value = (direction or "").strip()
    if value in CANONICAL_MATCH_DIRECTIONS:
        return value
    mapped = LEGACY_MATCH_DIRECTIONS.get(value)
    if mapped is not None:
        return mapped
    raise ValueError(f"unknown match_direction {direction!r}; expected one of {sorted(CANONICAL_MATCH_DIRECTIONS)}")


@dataclass(slots=True)
class MatchRequest:
    query: dict[str, Any]
    match_direction: str = MATCH_DIRECTION_SUPPLY_TO_BUYER
    top_n: int = 20
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "query": self.query,
            "match_direction": normalize_match_direction(self.match_direction),
            "top_n": self.top_n,
        }
        if self.odoo:
            data["odoo"] = self.odoo
        return data


@dataclass(slots=True)
class MatchCandidate:
    buyer_partner_id: int | None = None
    entity_ref: str | None = None
    buyer_name: str | None = None
    facility_profile_id: int | None = None
    score: float | None = None
    score_scale: str | None = None
    normalized_score: float | None = None
    eligible: bool = False
    rank: int | None = None
    reason: str | None = None
    typical_price: float | None = None
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    feature_contributions: list[Any] = field(default_factory=list)
    missing_evidence: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MatchResponse:
    status: str | None = None
    match_direction: str | None = None
    top_n: int | None = None
    results: list[MatchCandidate] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    query_id: str | None = None
    total_candidates: int | None = None
    execution_time_ms: int | None = None
    domain_spec_version: str | None = None
    model_version: str | None = None
    projection_version: str | None = None
    contract_version: str | None = None
    domain: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessWebLeadRequest:
    lead_id: str
    domain: str
    source: str
    raw_payload: dict[str, Any]
    normalized_seed: dict[str, Any]
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "lead_id": self.lead_id,
            "domain": self.domain,
            "source": self.source,
            "raw_payload": self.raw_payload,
            "normalized_seed": self.normalized_seed,
        }
        if self.odoo:
            data["odoo"] = self.odoo
        return data


@dataclass(slots=True)
class ProcessWebLeadResponse:
    status: str | None = None
    classification: dict[str, Any] = field(default_factory=dict)
    normalized: dict[str, Any] = field(default_factory=dict)
    intake_candidate: dict[str, Any] = field(default_factory=dict)
    recommended_action: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessIntakeRequest:
    intake_id: int
    domain: str
    intake_snapshot: dict[str, Any]
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "intake_id": self.intake_id,
            "domain": self.domain,
            "intake_snapshot": self.intake_snapshot,
        }
        if self.odoo:
            data["odoo"] = self.odoo
        return data


@dataclass(slots=True)
class ProcessIntakeResponse:
    status: str | None = None
    normalized: dict[str, Any] = field(default_factory=dict)
    match_query: dict[str, Any] = field(default_factory=dict)
    recommended_next_action: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

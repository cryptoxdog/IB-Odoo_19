"""Typed Odoo client-side contracts for Gate-routed intelligence calls."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .gate_config import DEFAULT_CONSENSUS_THRESHOLD


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

    Odoo identifiers ride in ``entity["_odoo_entity_id"]`` and the ``odoo``
    context metadata — never as Gate-level transforms.
    """

    entity: dict[str, Any] = field(default_factory=dict)
    object_type: str = "Account"
    objective: str = "Full entity enrichment and inference"
    max_variations: int = 5
    # Consumer-owned. Enrichment uses this both to accept a field and to skip
    # a later variation once the reply already clears it.
    consensus_threshold: float = DEFAULT_CONSENSUS_THRESHOLD
    # Per requested field. Absent means this request does not name field bars;
    # a present map is what Enrichment uses, with no engine default per field.
    field_thresholds: dict[str, float] | None = None
    kb_context: str | None = None
    # EnrichRequest.schema: the fields EIE should fill ({name: type}). EIE
    # targets ONLY these; without it EIE has nothing to enrich and echoes input.
    schema: dict[str, str] | None = None
    idempotency_key: str | None = None
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "entity": self.entity,
            "object_type": self.object_type,
            "objective": self.objective,
            "max_variations": self.max_variations,
            "consensus_threshold": self.consensus_threshold,
        }
        if self.field_thresholds:
            data["field_thresholds"] = self.field_thresholds
        if self.kb_context is not None:
            data["kb_context"] = self.kb_context
        if self.schema:
            data["schema"] = self.schema
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


@dataclass(slots=True)
class MatchRequest:
    query: dict[str, Any]
    # Must be a direction CEG's plasticos domain spec declares
    # (domains/plasticos/spec.yaml matchdirection); CEG rejects any other with
    # "No candidate entity for direction ...".
    match_direction: str = "supply_opportunity_to_buyer_facility"
    top_n: int = 20
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "query": self.query,
            "match_direction": self.match_direction,
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


# ── Converge contract v2 (EIE docs/contracts/converge/request.v2.md and
#    response.v2.md, both FROZEN 2026-11-13 incl. Revision 1) ───────────────

CONVERGE_REQUEST_V2 = "eie.converge.request/v2"
CONVERGE_RESPONSE_V2 = "eie.converge.response/v2"


@dataclass(frozen=True, slots=True)
class CartridgePin:
    id: str
    version: str
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {"id": self.id, "version": self.version}
        if self.sha256:
            data["sha256"] = self.sha256
        return data


@dataclass(frozen=True, slots=True)
class ConvergeRequestV2:
    """A converge request v2 body. ``schema`` and ``field_thresholds`` never appear."""

    cartridge: CartridgePin
    node: str
    subject_type: str
    subject_role: str | None
    targets: tuple[Mapping[str, Any], ...]
    observations: tuple[Mapping[str, Any], ...]
    entity: Mapping[str, Any]
    object_type: str
    objective: str
    max_variations: int
    consensus_threshold: float
    idempotency_key: str | None = None
    odoo: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def to_dict(self) -> dict[str, Any]:
        subject: dict[str, Any] = {"type": self.subject_type}
        if self.subject_role:
            subject["role"] = self.subject_role
        # Built pair by pair, not as one dict literal: these are wire member names,
        # not enum values (see gate_config.GateAvailabilityVerdict.as_dict).
        members: tuple[tuple[str, Any], ...] = (
            ("contract", CONVERGE_REQUEST_V2),
            ("cartridge", self.cartridge.to_dict()),
            ("node", self.node),
            ("subject", subject),
            ("targets", [_plain(t) for t in self.targets]),
            ("entity", _plain(self.entity)),
            ("object_type", self.object_type),
            ("objective", self.objective),
            ("max_variations", self.max_variations),
            ("consensus_threshold", self.consensus_threshold),
        )
        data: dict[str, Any] = dict(members)
        if self.observations:
            data["observations"] = [_plain(o) for o in self.observations]
        if self.idempotency_key is not None:
            data["idempotency_key"] = self.idempotency_key
        if self.odoo:
            data["odoo"] = _plain(self.odoo)
        return data


def _plain(value: Any) -> Any:
    """Deep-copy a frozen structure back into JSON-ready dicts and lists."""
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    return value


def freeze(value: Any) -> Any:
    """Deep-freeze JSON data: dicts become read-only mappings, lists tuples."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(freeze(v) for v in value)
    return value


thaw = _plain


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_type: str
    source_ref: str
    method: str
    independent: bool | None
    citations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceDerivation:
    method: str
    rule_or_model_version: str
    inputs: tuple[str, ...]
    kb_fragment_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceIdentity:
    subject_ref: str
    subject_type: str | None
    role: str | None


@dataclass(frozen=True, slots=True)
class ConflictCandidate:
    value: Any
    unit_status: str
    unit: str | None
    confidence: float | None
    sources: tuple[EvidenceSource, ...]


@dataclass(frozen=True, slots=True)
class FieldEvidence:
    """One response v2 ``field_evidence`` entry, validated and frozen.

    ``has_value`` separates "no value" from a JSON ``null`` value.
    """

    field: str
    state: str
    admitted: bool
    has_value: bool
    value: Any
    unit_status: str | None
    unit: str | None
    confidence: float | None
    sources: tuple[EvidenceSource, ...]
    derivation: EvidenceDerivation | None
    identity: EvidenceIdentity
    declaration: Mapping[str, Any]
    conflict: tuple[ConflictCandidate, ...] | None
    unknown_reason: str | None


@dataclass(frozen=True, slots=True)
class TypedProposal:
    proposal_id: str
    proposal_type: str
    identity: EvidenceIdentity
    fields: tuple[str, ...]
    admitted_fields: tuple[str, ...]
    review_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CartridgeResolution:
    cartridge_id: str
    cartridge_version: str
    cartridge_sha256: str
    node: str


@dataclass(frozen=True, slots=True)
class ConvergeResponseV2:
    """A parsed reply to a v2 request.

    ``rejection`` is set whenever the reply's evidence must not be used:
    a v1-shaped reply, an unrecognised contract or state, a requested field
    with no entry, a malformed entry, or a run that did not complete. When it
    is set, ``field_evidence`` and ``proposals`` are empty and nothing may be
    written (response.v2.md section 6, consumer rules).
    """

    contract_version: str | None
    state: str | None
    failure_reason: str | None
    resolution: CartridgeResolution | None
    field_evidence: Mapping[str, FieldEvidence]
    proposals: tuple[TypedProposal, ...]
    rejection: str | None

    @property
    def usable(self) -> bool:
        return self.rejection is None

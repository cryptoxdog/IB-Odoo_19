"""Typed response mappers for Gate payloads -> Odoo matcher shapes."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .gate_allowlists import (
    PARTNER_WRITEBACK_FIELD_ALLOWLIST,
    V2_CARTRIDGE_NODE,
    V2_KIND_BOOLEAN,
    V2_KIND_CHAR,
    V2_KIND_INTEGER,
    V2_KIND_MANY2MANY_CODE,
    V2_KIND_MANY2ONE_CODE,
    V2_KIND_SELECTION,
    V2_NUMERIC_KINDS,
    WEB_LEAD_WRITEBACK_FIELD_MAP,
    is_never_target,
    resolve_v2_target,
)
from .gate_contracts import (
    CONVERGE_RESPONSE_V2,
    CartridgePin,
    CartridgeResolution,
    ConflictCandidate,
    ConvergeRequestV2,
    ConvergeResponse,
    ConvergeResponseV2,
    EvidenceDerivation,
    EvidenceIdentity,
    EvidenceSource,
    FieldEvidence,
    MatchCandidate,
    MatchResponse,
    ProcessIntakeResponse,
    ProcessWebLeadResponse,
    TypedProposal,
    freeze,
)


def extract_audit_metadata(response_packet) -> dict[str, Any]:
    """Read correlation IDs from TransportPacket header, not flat payload."""
    header = response_packet.header
    return {
        "gate_packet_id": str(header.packet_id),
        "gate_correlation_id": header.correlation_id,
    }


BUYER_PARTNER_MODEL = "res.partner"
SCORE_SCALE_0_TO_1 = "0_to_1"
SCORE_SCALE_0_TO_100 = "0_to_100"
_ENTITY_REF_RE = re.compile(r"^(?P<model>[a-z0-9_.-]+):(?P<id>\S+)$")


class UnresolvableBuyerRef(ValueError):
    """Raised internally when an entity_ref cannot map to a res.partner id."""


def resolve_buyer_partner_id(entity_ref: str | None) -> int:
    """Resolve a CEG contract entity_ref to an Odoo res.partner integer id.

    DEC-001/OPTION-B: entity_ref is "<model>:<id>" (e.g. "res.partner:102").
    Accept ONLY the res.partner model; anything else fails safe.
    """
    if not entity_ref or not isinstance(entity_ref, str):
        raise UnresolvableBuyerRef("candidate has no entity_ref")
    match = _ENTITY_REF_RE.match(entity_ref.strip())
    if not match:
        raise UnresolvableBuyerRef(f"entity_ref does not match '<model>:<id>': {entity_ref!r}")
    model, raw_id = match.group("model"), match.group("id")
    if model != BUYER_PARTNER_MODEL:
        raise UnresolvableBuyerRef(f"entity_ref model {model!r} is not {BUYER_PARTNER_MODEL!r}: {entity_ref!r}")
    try:
        return int(raw_id)
    except (TypeError, ValueError) as exc:
        raise UnresolvableBuyerRef(f"entity_ref id is not an integer: {entity_ref!r}") from exc


def normalize_score(score: float | None, score_scale: str | None) -> float | None:
    """Normalize a candidate score to [0, 1] using the declared score_scale.

    None score -> None. 0_to_100 is divided by 100; 0_to_1 is clamped;
    unnormalized_declared or unknown scales are left as-is (no fabricated scale).
    """
    if score is None:
        return None
    if score_scale == SCORE_SCALE_0_TO_1:
        return max(0.0, min(1.0, float(score)))
    if score_scale == SCORE_SCALE_0_TO_100:
        return max(0.0, min(1.0, float(score) / 100.0))
    return float(score)


def map_match_response(payload: dict[str, Any]) -> MatchResponse:
    """Map a CEG match response payload into Odoo buyer-match candidates.

    Reads "candidates" (never "results"). Candidate identity is resolved from
    entity_ref via resolve_buyer_partner_id() (DEC-001/OPTION-B); a missing,
    malformed, foreign-namespace, or non-integer ref FAILS SAFE: the candidate
    is skipped and recorded in unresolved, never mis-attributed. Envelope
    lineage (query_id etc.) is preserved on the response, not invented per
    candidate.
    """
    candidates = payload.get("candidates")
    if candidates is None:
        raise KeyError(f"CEG match payload has no 'candidates' key (got keys: {sorted(payload)})")

    results: list[MatchCandidate] = []
    unresolved: list[dict[str, Any]] = []
    for cand in candidates:
        entity_ref = cand.get("entity_ref")
        try:
            buyer_partner_id = resolve_buyer_partner_id(entity_ref)
        except UnresolvableBuyerRef as exc:
            unresolved.append({"entity_ref": entity_ref, "reason": str(exc)})
            continue
        # CEG eligibility must be explicit: hard-gate failures (eligible=false)
        # AND missing/non-True eligibility both fail closed — never surface as
        # selectable matches.
        if cand.get("eligible") is not True:
            unresolved.append(
                {
                    "entity_ref": entity_ref,
                    "reason": (
                        "candidate not eligible (hard gates failed)"
                        if cand.get("eligible") is False
                        else "candidate eligibility missing or not explicit True"
                    ),
                    "failed_gates": list(cand.get("failed_gates") or [])
                    if not isinstance(cand.get("failed_gates"), int)
                    else [],
                }
            )
            continue
        failed_gates = cand.get("failed_gates") or []
        if isinstance(failed_gates, int):
            failed_gates = []
        results.append(
            MatchCandidate(
                buyer_partner_id=buyer_partner_id,
                entity_ref=entity_ref,
                score=cand.get("score"),
                score_scale=cand.get("score_scale"),
                normalized_score=normalize_score(cand.get("score"), cand.get("score_scale")),
                eligible=bool(cand.get("eligible", False)),
                rank=cand.get("rank"),
                reason=cand.get("explanation"),
                gates_passed=[],
                gates_failed=list(failed_gates),
                feature_contributions=list(cand.get("feature_contributions") or []),
                missing_evidence=list(cand.get("missing_evidence") or []),
                raw=cand,
            )
        )
    results.sort(
        key=lambda item: (item.normalized_score is not None, item.normalized_score or 0.0),
        reverse=True,
    )
    return MatchResponse(
        status=payload.get("status"),
        match_direction=payload.get("direction"),
        top_n=payload.get("top_n"),
        results=results,
        unresolved=unresolved,
        query_id=payload.get("query_id"),
        total_candidates=payload.get("total_candidates", len(candidates)),
        execution_time_ms=payload.get("execution_time_ms"),
        domain_spec_version=payload.get("domain_spec_version"),
        model_version=payload.get("model_version"),
        projection_version=payload.get("projection_version"),
        contract_version=payload.get("contract_version"),
        domain=payload.get("domain"),
        raw=payload,
    )


def map_match_response_to_matcher_dicts(
    mapped: MatchResponse,
    *,
    audit_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Convert Gate match response to plasticos.buyer.matcher result dicts."""
    audit = audit_metadata or {}
    results: list[dict[str, Any]] = []
    for item in mapped.results:
        if not item.buyer_partner_id:
            continue
        if not item.eligible:
            continue
        # Missing evidence stays missing: a candidate Gate scored as None is not
        # a zero, an unknown price is not 0.0, and an absent facility is omitted.
        row = {
            "buyer_id": int(item.buyer_partner_id),
            "buyer_name": item.buyer_name,
            "total_score": item.normalized_score,
            "typical_price": item.typical_price,
            "gates_passed": item.gates_passed,
            "gates_failed": item.gates_failed,
            "match_details": item.raw,
            "reason": item.reason,
            "match_source": "gate",
            "gate_packet_id": audit.get("gate_packet_id"),
            "gate_correlation_id": audit.get("gate_correlation_id"),
        }
        if item.facility_profile_id:
            row["facility_profile_id"] = item.facility_profile_id
        results.append(row)
    results.sort(
        key=lambda row: (row.get("total_score") is not None, row.get("total_score") or 0.0),
        reverse=True,
    )
    return results


EIE_STATE_COMPLETED = "completed"
SDK_FAILURE_STATUS = "failed"


def _sdk_failure_reason(payload: dict[str, Any]) -> str | None:
    """The reason a Gate_SDK failure packet carries, or None.

    When the node handler raises, the SDK runtime answers with a failure packet
    whose payload is ``{"status": "failed", "error": <exception class>,
    "message": <client message>, "packet_id": ...}``
    (``constellation_node_sdk.runtime.execution.create_error_transport_packet``).
    It has no ``state`` or ``failure_reason``. Without this, the operator saw
    only ``failed`` and lost the reason EIE gave.
    """
    if payload.get("status") != SDK_FAILURE_STATUS:
        return None
    error = payload.get("error")
    message = payload.get("message")
    error = error.strip() if isinstance(error, str) else ""
    message = message.strip() if isinstance(message, str) else ""
    if error and message and message != error:
        return f"{error}: {message}"
    return error or message or None


def map_converge_response(payload: dict[str, Any]) -> ConvergeResponse:
    """Map an EIE EnrichResponse into Odoo-storable fields WITHOUT fabrication.

    Every EnrichResponse field is carried through (no field loss). Cost is
    ``tokens_used``; ``total_cost_usd`` and ``writeback_applied`` stay
    explicitly UNAVAILABLE (None) — never fabricated (DNB-006). ``status`` is
    derived from EIE ``state``/``failure_reason`` for the Odoo consumer's
    usable-result check. A Gate_SDK failure packet (``status: failed`` with
    ``error``/``message``) supplies ``failure_reason`` when EIE sent none.
    """
    # Require an explicit completed state — never manufacture completed/ok on
    # empty, partial, or version-skewed payloads that omit state.
    raw_state = payload.get("state")
    state = raw_state if isinstance(raw_state, str) and raw_state.strip() else None
    failure_reason = payload.get("failure_reason") or _sdk_failure_reason(payload)
    if state == EIE_STATE_COMPLETED and not failure_reason:
        status = "ok"
    else:
        status = failure_reason or state or "failed"
    return ConvergeResponse(
        status=status,
        state=state,
        failure_reason=failure_reason,
        final_fields=payload.get("fields") or {},
        pass_count=payload.get("pass_count"),
        variation_count=payload.get("variation_count"),
        confidence=payload.get("confidence"),
        consensus_threshold=payload.get("consensus_threshold"),
        uncertainty_score=payload.get("uncertainty_score"),
        processing_time_ms=payload.get("processing_time_ms"),
        quality_tier=payload.get("quality_tier"),
        inference_version=payload.get("inference_version"),
        kb_content_hash=payload.get("kb_content_hash"),
        kb_files_consulted=list(payload.get("kb_files_consulted") or []),
        kb_fragment_ids=list(payload.get("kb_fragment_ids") or []),
        inferences=list(payload.get("inferences") or []),
        grade_matches=list(payload.get("grade_matches") or []),
        enrichment_payload=payload.get("enrichment_payload"),
        feature_vector=payload.get("feature_vector"),
        tokens_used=payload.get("tokens_used"),
        total_cost_usd=None,
        writeback_applied=None,
        raw=payload,
    )


def partner_writeback_from_converge(resp: ConvergeResponse) -> dict[str, Any]:
    """Derive the Odoo-side proposal from EIE fields (allowlisted only).

    EIE converge performs no writeback itself; the proposal is an Odoo-side
    review artifact derived from ``final_fields``, never a fabricated response
    field.
    """
    source = resp.final_fields or {}
    return {k: v for k, v in source.items() if k in PARTNER_WRITEBACK_FIELD_ALLOWLIST and v not in (None, False, "")}


def map_web_lead_response(payload: dict[str, Any]) -> ProcessWebLeadResponse:
    return ProcessWebLeadResponse(
        status=payload.get("status"),
        classification=payload.get("classification") or {},
        normalized=payload.get("normalized") or {},
        intake_candidate=payload.get("intake_candidate") or {},
        recommended_action=payload.get("recommended_action"),
        raw=payload,
    )


def web_lead_writeback(resp: ProcessWebLeadResponse, lead_model) -> dict[str, Any]:
    vals: dict[str, Any] = {}
    for payload_key, field_name in WEB_LEAD_WRITEBACK_FIELD_MAP.items():
        if field_name in lead_model._fields:
            value = resp.normalized.get(payload_key)
            if value not in (None, False, ""):
                vals[field_name] = value
    if "ai_normalized" in lead_model._fields:
        vals["ai_normalized"] = resp.normalized
    if "ai_analysis" in lead_model._fields:
        vals["ai_analysis"] = resp.raw
    if "decision" in lead_model._fields:
        temp = resp.classification.get("temperature")
        if temp in {"hot", "cold"}:
            vals["decision"] = temp
    return vals


def map_intake_response(payload: dict[str, Any]) -> ProcessIntakeResponse:
    return ProcessIntakeResponse(
        status=payload.get("status"),
        normalized=payload.get("normalized") or {},
        match_query=payload.get("match_query") or {},
        recommended_next_action=payload.get("recommended_next_action"),
        raw=payload,
    )


# ── Converge response v2 (EIE docs/contracts/converge/response.v2.md, FROZEN
#    2026-11-13 incl. Revision 1) ─────────────────────────────────────────────
#
# The parser is a validator, not a repairer: any reply it cannot fully account
# for is rejected as a whole, its evidence unused, and the reason recorded
# (consumer rule, section 6). Nothing is defaulted, coerced or read from
# ``fields`` alone as if it were evidenced (L9-UNKNOWN-001).

V2_STATE_OBSERVED = "observed"
V2_STATE_INFERRED = "inferred"
V2_STATE_EXTERNAL_CLAIM = "external_claim"
V2_STATE_CONFLICTING = "conflicting"
V2_STATE_UNKNOWN = "unknown"
V2_EVIDENCE_STATES = frozenset(
    {V2_STATE_OBSERVED, V2_STATE_INFERRED, V2_STATE_EXTERNAL_CLAIM, V2_STATE_CONFLICTING, V2_STATE_UNKNOWN}
)
V2_VALUE_STATES = frozenset({V2_STATE_OBSERVED, V2_STATE_INFERRED, V2_STATE_EXTERNAL_CLAIM})
# Approved write policy (operator decision): only these states, and only when admitted.
V2_WRITABLE_STATES = frozenset({V2_STATE_INFERRED, V2_STATE_EXTERNAL_CLAIM})
V2_RUN_STATES = frozenset({"completed", "degraded", "failed"})
V2_UNIT_STATED = "stated"
V2_UNIT_STATUSES = frozenset({V2_UNIT_STATED, "not_applicable", "unknown"})
V2_SOURCE_TYPES = frozenset({"request_entity", "request_observation", "provider", "kb", "graph"})
V2_UNKNOWN_REASONS = frozenset({"no_evidence", "source_unavailable", "budget_exhausted", "not_attempted"})
V2_REVIEW_REASONS = frozenset(
    {
        "contains_external_claim",
        "contains_inferred",
        "contains_conflict",
        "contains_unknown",
        "contains_unadmitted",
    }
)

V2_REJECT_V1_REPLY = "v1_reply"
V2_REJECT_UNSUPPORTED_CONTRACT = "unsupported_contract_version"
V2_REJECT_NOT_COMPLETED = "not_completed"
V2_REJECT_MALFORMED = "malformed_response"
V2_REJECT_MISSING_ENTRY = "missing_field_evidence"
V2_REJECT_RESOLUTION = "resolution_mismatch"


class _Malformed(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


def _need(condition: bool, detail: str, code: str = V2_REJECT_MALFORMED) -> None:
    if not condition:
        raise _Malformed(code, detail)


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _confidence(value: Any, where: str) -> float | None:
    if value is None:
        return None
    _need(_is_number(value) and 0.0 <= float(value) <= 1.0, f"{where}.confidence is not null or a number in [0, 1]")
    return float(value)


def _source(raw: Any, where: str) -> EvidenceSource:
    _need(isinstance(raw, dict), f"{where} is not an object")
    _need(raw.get("source_type") in V2_SOURCE_TYPES, f"{where}.source_type {raw.get('source_type')!r} is unrecognised")
    _need(_is_str(raw.get("source_ref")), f"{where}.source_ref is missing")
    _need(_is_str(raw.get("method")), f"{where}.method is missing")
    _need("independent" in raw, f"{where}.independent is missing")
    _need(raw["independent"] is None or isinstance(raw["independent"], bool), f"{where}.independent is not bool/null")
    citations = raw.get("citations", [])
    _need(isinstance(citations, list) and all(_is_str(c) for c in citations), f"{where}.citations is malformed")
    return EvidenceSource(raw["source_type"], raw["source_ref"], raw["method"], raw["independent"], tuple(citations))


def _sources(raw: Any, where: str) -> tuple[EvidenceSource, ...]:
    _need(isinstance(raw, list), f"{where}.sources is not a list")
    return tuple(_source(item, f"{where}.sources[{i}]") for i, item in enumerate(raw))


def _identity(raw: Any, where: str, expected: EvidenceIdentity) -> EvidenceIdentity:
    _need(isinstance(raw, dict), f"{where}.identity is not an object")
    for key in ("subject_ref", "subject_type", "role"):
        _need(key in raw, f"{where}.identity.{key} is missing")
    identity = EvidenceIdentity(raw["subject_ref"], raw["subject_type"], raw["role"])
    _need(identity == expected, f"{where}.identity {identity} is not the requested subject {expected}")
    return identity


def _unit_fields(raw: dict, where: str) -> tuple[str, str | None]:
    unit_status = raw.get("unit_status")
    _need(unit_status in V2_UNIT_STATUSES, f"{where}.unit_status {unit_status!r} is unrecognised")
    if unit_status == V2_UNIT_STATED:
        _need(_is_str(raw.get("unit")), f"{where}.unit must be stated")
        return unit_status, raw["unit"]
    _need(raw.get("unit") is None, f"{where}.unit present without unit_status 'stated'")
    return unit_status, None


def _entry(name: str, raw: Any, expected: EvidenceIdentity) -> FieldEvidence:
    where = f"field_evidence.{name}"
    _need(isinstance(raw, dict), f"{where} is not an object")
    state = raw.get("state")
    _need(state in V2_EVIDENCE_STATES, f"{where}.state {state!r} is unrecognised")
    admitted = raw.get("admitted")
    _need(isinstance(admitted, bool), f"{where}.admitted is not a boolean")
    _need(not admitted or state in V2_WRITABLE_STATES, f"{where} is admitted in state {state!r}")
    has_value = "value" in raw
    unit_status = unit = None
    if state in V2_VALUE_STATES:
        _need(has_value, f"{where} carries no value in state {state!r}")
        unit_status, unit = _unit_fields(raw, where)
    else:
        _need(not has_value, f"{where} carries a value in state {state!r}")
        _need("unit_status" not in raw and "unit" not in raw, f"{where} carries a unit in state {state!r}")
    _need("confidence" in raw, f"{where}.confidence is missing")
    confidence = _confidence(raw["confidence"], where)
    if state in (V2_STATE_UNKNOWN, V2_STATE_CONFLICTING):
        _need(confidence is None, f"{where}.confidence must be null in state {state!r}")
    sources = _sources(raw.get("sources"), where)
    if state in (V2_STATE_OBSERVED, V2_STATE_EXTERNAL_CLAIM):
        _need(bool(sources), f"{where}.sources must be non-empty in state {state!r}")
    _need("derivation" in raw, f"{where}.derivation is missing")
    derivation = None
    if state == V2_STATE_INFERRED:
        d = raw["derivation"]
        _need(isinstance(d, dict), f"{where}.derivation must be set for an inferred value")
        _need(
            _is_str(d.get("method")) and _is_str(d.get("rule_or_model_version")), f"{where}.derivation is untraceable"
        )
        inputs = d.get("inputs")
        kb_ids = d.get("kb_fragment_ids")
        _need(isinstance(inputs, list) and all(_is_str(i) for i in inputs), f"{where}.derivation.inputs is malformed")
        _need(
            isinstance(kb_ids, list) and all(_is_str(i) for i in kb_ids),
            f"{where}.derivation.kb_fragment_ids is malformed",
        )
        derivation = EvidenceDerivation(d["method"], d["rule_or_model_version"], tuple(inputs), tuple(kb_ids))
    else:
        _need(raw["derivation"] is None, f"{where}.derivation must be null in state {state!r}")
    identity = _identity(raw.get("identity"), where, expected)
    declaration = raw.get("declaration")
    _need(isinstance(declaration, dict) and _is_str(declaration.get("type")), f"{where}.declaration is missing")
    _need("conflict" in raw, f"{where}.conflict is missing")
    conflict = None
    if state == V2_STATE_CONFLICTING:
        c = raw["conflict"]
        _need(
            isinstance(c, dict) and c.get("resolution", "absent") is None,
            f"{where}.conflict must carry resolution null",
        )
        candidates = c.get("candidates")
        _need(isinstance(candidates, list) and len(candidates) >= 2, f"{where}.conflict needs at least two candidates")
        parsed = []
        for i, cand in enumerate(candidates):
            cw = f"{where}.conflict.candidates[{i}]"
            _need(isinstance(cand, dict) and "value" in cand, f"{cw} carries no value")
            c_status, c_unit = _unit_fields(cand, cw)
            parsed.append(
                ConflictCandidate(
                    freeze(cand["value"]),
                    c_status,
                    c_unit,
                    _confidence(cand.get("confidence"), cw),
                    _sources(cand.get("sources"), cw),
                )
            )
        conflict = tuple(parsed)
    else:
        _need(raw["conflict"] is None, f"{where}.conflict must be null in state {state!r}")
    _need("unknown_reason" in raw, f"{where}.unknown_reason is missing")
    if state == V2_STATE_UNKNOWN:
        _need(raw["unknown_reason"] in V2_UNKNOWN_REASONS, f"{where}.unknown_reason {raw['unknown_reason']!r}")
    else:
        _need(raw["unknown_reason"] is None, f"{where}.unknown_reason must be null in state {state!r}")
    return FieldEvidence(
        field=name,
        state=state,
        admitted=admitted,
        has_value=has_value,
        value=freeze(raw.get("value")),
        unit_status=unit_status,
        unit=unit,
        confidence=confidence,
        sources=sources,
        derivation=derivation,
        identity=identity,
        declaration=freeze(declaration),
        conflict=conflict,
        unknown_reason=raw["unknown_reason"],
    )


def _proposal(raw: Any, i: int, entries: dict[str, FieldEvidence], expected: EvidenceIdentity) -> TypedProposal:
    where = f"proposals[{i}]"
    _need(isinstance(raw, dict), f"{where} is not an object")
    _need(_is_str(raw.get("proposal_id")) and _is_str(raw.get("proposal_type")), f"{where} has no id or type")
    names = raw.get("fields")
    admitted = raw.get("admitted_fields")
    _need(isinstance(names, list) and all(n in entries for n in names), f"{where}.fields names an unknown entry")
    _need(isinstance(admitted, list) and set(admitted) <= set(names), f"{where}.admitted_fields is not a subset")
    _need(
        set(admitted) == {n for n in names if entries[n].admitted},
        f"{where}.admitted_fields disagrees with field_evidence",
    )
    review = raw.get("review")
    _need(isinstance(review, dict) and review.get("required") is True, f"{where}.review.required is not true")
    reasons = review.get("reasons")
    _need(isinstance(reasons, list) and set(reasons) <= V2_REVIEW_REASONS, f"{where}.review.reasons is malformed")
    return TypedProposal(
        raw["proposal_id"],
        raw["proposal_type"],
        _identity(raw.get("identity"), where, expected),
        tuple(names),
        tuple(admitted),
        tuple(reasons),
    )


def _rejected(payload: dict[str, Any], code: str, detail: str) -> ConvergeResponseV2:
    raw_version = payload.get("contract_version")
    raw_state = payload.get("state")
    return ConvergeResponseV2(
        contract_version=raw_version if isinstance(raw_version, str) else None,
        state=raw_state if isinstance(raw_state, str) else None,
        failure_reason=payload.get("failure_reason") if isinstance(payload.get("failure_reason"), str) else None,
        resolution=None,
        field_evidence=MappingProxyType({}),
        proposals=(),
        rejection=f"{code}: {detail}",
    )


def parse_converge_response_v2(payload: Any, *, request: ConvergeRequestV2) -> ConvergeResponseV2:
    """Parse a reply to ``request`` into immutable evidence, or reject it whole.

    A reply without ``contract_version`` is v1 (response.v2.md section 6;
    EIE main answers a v2 request in v2 since 8c02aa9) and is rejected for v2 use: its ``fields``
    are not evidence. Only a ``completed`` run is usable; ``degraded`` and
    ``failed`` replies are rejected with their reason.
    """
    expected = EvidenceIdentity(request.entity.get("id"), request.subject_type, request.subject_role)
    requested = [t["field"] for t in request.targets]
    return _parse_v2(payload, expected=expected, pin=request.cartridge, node=request.node, requested=requested)


def parse_sweep_converge_response_v2(
    payload: Any, *, entity_id: str, pin: CartridgePin, node: str = V2_CARTRIDGE_NODE
) -> ConvergeResponseV2:
    """Parse one enrichment-sweep result's converge v2 body, with no Odoo-built request.

    EIE builds the sweep's converge request itself (enrichment-sweep.md 3.4
    step 5): targets from CEG readiness gaps, the tenant's pinned cartridge, the
    candidate's node, no ``subject``. So the reply is validated against its own
    resolution echo, which must equal Odoo's configured pin (id, version and
    sha256) and ``node``, and against the candidate: every identity names
    ``entity_id`` with no subject type or role (response.v2.md section 9.2).
    Every other check of ``parse_converge_response_v2`` applies unchanged; only
    "every requested field has an entry" has nothing to check against.
    """
    if not pin.sha256:
        return _rejected({}, V2_REJECT_RESOLUTION, "a sweep result needs a cartridge sha256 pin to compare")
    return _parse_v2(payload, expected=EvidenceIdentity(entity_id, None, None), pin=pin, node=node, requested=())


def _parse_v2(
    payload: Any, *, expected: EvidenceIdentity, pin: CartridgePin, node: str, requested
) -> ConvergeResponseV2:
    if not isinstance(payload, dict):
        return _rejected({}, V2_REJECT_MALFORMED, "reply payload is not an object")
    version = payload.get("contract_version")
    if version is None:
        reason = payload.get("failure_reason") or _sdk_failure_reason(payload) or payload.get("state") or "no state"
        return _rejected(payload, V2_REJECT_V1_REPLY, f"reply carries no contract_version ({reason})")
    if version != CONVERGE_RESPONSE_V2:
        return _rejected(payload, V2_REJECT_UNSUPPORTED_CONTRACT, repr(version))
    state = payload.get("state")
    if not isinstance(state, str) or state not in V2_RUN_STATES:
        return _rejected(payload, V2_REJECT_MALFORMED, f"run state {state!r} is unrecognised")
    if state != EIE_STATE_COMPLETED or payload.get("failure_reason"):
        return _rejected(payload, V2_REJECT_NOT_COMPLETED, f"{state}: {payload.get('failure_reason') or 'no reason'}")

    try:
        res = payload.get("resolution")
        _need(isinstance(res, dict), "resolution is missing")
        for key in ("cartridge_id", "cartridge_version", "cartridge_sha256", "node"):
            _need(_is_str(res.get(key)), f"resolution.{key} is missing")
        resolution = CartridgeResolution(
            res["cartridge_id"], res["cartridge_version"], res["cartridge_sha256"], res["node"]
        )
        _need(
            (resolution.cartridge_id, resolution.cartridge_version, resolution.node) == (pin.id, pin.version, node)
            and (not pin.sha256 or pin.sha256 == resolution.cartridge_sha256),
            f"resolved {resolution} is not the pinned {pin} / node {node}",
            V2_REJECT_RESOLUTION,
        )
        raw_evidence = payload.get("field_evidence")
        _need(isinstance(raw_evidence, dict), "field_evidence is missing")
        for name in requested:
            _need(
                name in raw_evidence, f"no field_evidence entry for requested field {name!r}", V2_REJECT_MISSING_ENTRY
            )
        entries = {name: _entry(name, raw, expected) for name, raw in raw_evidence.items()}
        for entry in entries.values():
            if entry.derivation:
                missing = [i for i in entry.derivation.inputs if i not in entries]
                _need(not missing, f"field_evidence.{entry.field}.derivation.inputs {missing} have no entry")
        fields_ = payload.get("fields")
        _need(isinstance(fields_, dict), "fields is missing")
        admitted = {name for name, entry in entries.items() if entry.admitted}
        _need(set(fields_) == admitted, "fields keys are not exactly the admitted entries")
        for name in admitted:
            _need(freeze(fields_[name]) == entries[name].value, f"fields[{name!r}] differs from its evidence value")
        raw_proposals = payload.get("proposals")
        _need(isinstance(raw_proposals, list), "proposals is missing")
        proposals = tuple(_proposal(p, i, entries, expected) for i, p in enumerate(raw_proposals))
    except _Malformed as exc:
        return _rejected(payload, exc.code, str(exc).split(": ", 1)[1])
    except TypeError as exc:
        # An unhashable JSON value (list or object) where a string was due
        # fails a membership test; it is a malformed reply, never a crash.
        return _rejected(payload, V2_REJECT_MALFORMED, f"value of the wrong JSON type: {exc}")
    return ConvergeResponseV2(
        contract_version=version,
        state=state,
        failure_reason=None,
        resolution=resolution,
        field_evidence=MappingProxyType(entries),
        proposals=proposals,
        rejection=None,
    )


# ── Converge v2 writeback plan (pure; the Odoo writer resolves codes,
#    applies merge-not-overwrite and records provenance) ─────────────────────

V2_PLAN_WRITE = "write"
V2_PLAN_SKIP = "skip"
V2_SKIP_UNKNOWN = "unknown"
V2_SKIP_CONFLICTING = "conflicting"
V2_SKIP_UNIT = "unit"
V2_SKIP_NOT_ADMITTED = "not_admitted"


@dataclass(frozen=True, slots=True)
class V2WritebackDecision:
    """What to do with one requested cartridge field.

    For a write, ``value`` is already in the Odoo field's unit; for a code row
    it is the code (many2one) or a tuple of codes (many2many), still to be
    resolved against existing master records.
    """

    cartridge_field: str
    odoo_field: str
    kind: str
    action: str
    value: Any = None
    skip_reason: str | None = None
    detail: str | None = None
    evidence_state: str | None = None
    confidence: float | None = None
    # For a converted number: the value and governing unit as the reply stated them.
    source_value: Any = None
    source_unit: str | None = None


@dataclass(frozen=True, slots=True)
class V2WritebackPlan:
    target: str
    odoo_model: str
    decisions: tuple[V2WritebackDecision, ...]
    rejection: str | None

    @property
    def writes(self) -> tuple[V2WritebackDecision, ...]:
        return tuple(d for d in self.decisions if d.action == V2_PLAN_WRITE)


# Declaration keys that are not part of the typed shape being compared.
_DECL_IGNORED_KEYS = frozenset({"required", "unit"})
_DECL_PROPERTIES = "properties"


def _declaration_shape(decl: Any) -> Any:
    """Compare declarations as the engine does (``spec_types.shape``), ``required`` and ``unit`` aside.

    The engine emits a map's ``properties`` as an object keyed by property
    name; the cartridge spec writes them as a list of ``{name, ...}``. Both
    normalise to the keyed form, so the same declaration compares equal.
    """
    if isinstance(decl, Mapping):
        shaped = {}
        for key, value in decl.items():
            if key in _DECL_IGNORED_KEYS:
                continue
            if key == _DECL_PROPERTIES and isinstance(value, tuple | list):
                value = {
                    p.get("name"): {k: v for k, v in p.items() if k != "name"} for p in value if isinstance(p, Mapping)
                }
            shaped[key] = _declaration_shape(value)
        return shaped
    if isinstance(decl, tuple | list):
        return [_declaration_shape(v) for v in decl]
    return decl


def governing_unit(entry: FieldEvidence) -> str | None:
    """The unit a number is read in (decision 4 as amended 2026-11-13).

    The value's own unit when ``unit_status`` is ``stated``; otherwise the unit
    the cartridge declares for the field (response.v2.md 10.2,
    ``declaration.unit``); otherwise none, and the number is not written.
    """
    if entry.unit_status == V2_UNIT_STATED and entry.unit:
        return entry.unit
    declared = entry.declaration.get(_DECL_UNIT) if isinstance(entry.declaration, Mapping) else None
    return declared if isinstance(declared, str) and declared.strip() else None


_DECL_UNIT = "unit"


def _coerce(row, entry: FieldEvidence) -> tuple[str, Any, str | None]:
    """Return (action, value, detail) for an admitted writable entry, or raise _Malformed."""
    value = entry.value
    where = f"field_evidence.{entry.field}.value"
    if row.kind in V2_NUMERIC_KINDS:
        _need(_is_number(value), f"{where} is not a finite number")
        unit = governing_unit(entry)
        if unit is None:
            return V2_PLAN_SKIP, None, "no governing unit (value states none and the declaration declares none)"
        if unit not in row.units:
            return V2_PLAN_SKIP, None, f"unit {unit!r} is not one of {sorted(row.units)}"
        converted = float(value) * row.units[unit]
        if row.kind == V2_KIND_INTEGER:
            if row.round_to_integer:
                converted = math.floor(converted + 0.5)
            elif not converted.is_integer():
                return V2_PLAN_SKIP, None, f"{value} {unit} is not a whole number in the Odoo unit"
            converted = int(converted)
        return V2_PLAN_WRITE, converted, unit
    if row.kind == V2_KIND_BOOLEAN:
        _need(isinstance(value, bool), f"{where} is not a boolean")
        return V2_PLAN_WRITE, value, None
    if row.kind in (V2_KIND_CHAR, V2_KIND_SELECTION, V2_KIND_MANY2ONE_CODE):
        _need(_is_str(value), f"{where} is not a non-empty string")
        return V2_PLAN_WRITE, value.strip(), None
    if row.kind == V2_KIND_MANY2MANY_CODE:
        _need(isinstance(value, tuple) and value, f"{where} is not a non-empty list")
        codes = []
        for item in value:
            code = item.get(row.code_item_key) if row.code_item_key and isinstance(item, Mapping) else item
            _need(_is_str(code), f"{where} carries an item without a code")
            codes.append(code.strip())
        return V2_PLAN_WRITE, tuple(dict.fromkeys(codes)), None
    raise _Malformed(V2_REJECT_MALFORMED, f"{row.kind} has no coercion")  # pragma: no cover - V2_KINDS is closed


def plan_converge_v2_writeback(
    target: str, response: ConvergeResponseV2, request: ConvergeRequestV2, field_defs=None
) -> V2WritebackPlan:
    """Decide, per requested field, what the approved evidence-state policy allows.

    Writes only admitted ``inferred`` / ``external_claim`` values whose shape
    matches the reviewed row and whose number carries an accepted unit.
    ``unknown`` and ``conflicting`` are skipped and recorded; an ``observed``
    or unadmitted value is skipped as not admitted. A rejected response, a
    declaration that no longer matches the row, or a value of the wrong shape
    rejects the plan: nothing is written. The facility profile target is
    derived from ``field_defs`` exactly as the request builder derived it.
    """
    spec = resolve_v2_target(target, field_defs, subject=request.subject_type, version=request.cartridge.version)
    if not response.usable:
        return V2WritebackPlan(target, spec.odoo_model, (), response.rejection)
    decisions = []
    try:
        for requested in request.targets:
            row = spec.row(requested["field"])
            _need(row is not None, f"requested field {requested['field']!r} has no mapping row")
            _need(not is_never_target(row.odoo_field), f"{row.odoo_field} is never a converge target")
            entry = response.field_evidence[row.cartridge_field]
            decisions.append(_decide(row, entry))
    except _Malformed as exc:
        return V2WritebackPlan(target, spec.odoo_model, (), str(exc))
    return V2WritebackPlan(target, spec.odoo_model, tuple(decisions), None)


def _decide(row, entry: FieldEvidence) -> V2WritebackDecision:
    """The evidence-state write policy for one mapped field (shared by interactive runs and the sweep)."""
    _need(
        _declaration_shape(entry.declaration) == _declaration_shape(row.declaration),
        f"cartridge declaration of {row.cartridge_field!r} differs from the reviewed row",
    )
    base = {
        "cartridge_field": row.cartridge_field,
        "odoo_field": row.odoo_field,
        "kind": row.kind,
        "evidence_state": entry.state,
        "confidence": entry.confidence,
    }
    if entry.state == V2_STATE_UNKNOWN:
        return V2WritebackDecision(
            **base, action=V2_PLAN_SKIP, skip_reason=V2_SKIP_UNKNOWN, detail=entry.unknown_reason
        )
    if entry.state == V2_STATE_CONFLICTING:
        detail = f"{len(entry.conflict or ())} disagreeing candidates"
        return V2WritebackDecision(**base, action=V2_PLAN_SKIP, skip_reason=V2_SKIP_CONFLICTING, detail=detail)
    if not entry.admitted or entry.state not in V2_WRITABLE_STATES:
        return V2WritebackDecision(
            **base, action=V2_PLAN_SKIP, skip_reason=V2_SKIP_NOT_ADMITTED, detail=f"state {entry.state}"
        )
    action, value, detail = _coerce(row, entry)
    if action == V2_PLAN_SKIP:
        return V2WritebackDecision(**base, action=V2_PLAN_SKIP, skip_reason=V2_SKIP_UNIT, detail=detail)
    if row.kind in V2_NUMERIC_KINDS:
        return V2WritebackDecision(
            **base, action=V2_PLAN_WRITE, value=value, source_value=entry.value, source_unit=detail
        )
    return V2WritebackDecision(**base, action=V2_PLAN_WRITE, value=value)


V2_SKIP_UNMAPPED = "unmapped"


def plan_sweep_converge_v2_writeback(response: ConvergeResponseV2, spec, unmapped=None) -> V2WritebackPlan:
    """The write policy over every field a sweep result carries evidence for.

    EIE chose the targets (enrichment-sweep.md 3.4 step 4), so the plan walks
    the reply's ``field_evidence``, not an Odoo request. ``spec`` is the
    facility-profile target derived for the union of the cartridge's subjects
    (``derive_facility_profile_target_all_subjects``), so any field EIE
    targeted can be reviewed. A field with no reviewed row (undeclared,
    unmapped or a never target) is skipped and recorded as ``unmapped``; every
    mapped field gets exactly the interactive decision (``_decide``).
    """
    if not response.usable:
        return V2WritebackPlan(spec.key, spec.odoo_model, (), response.rejection)
    unmapped = unmapped or {}
    decisions = []
    try:
        for name in sorted(response.field_evidence):
            entry = response.field_evidence[name]
            row = spec.row(name)
            if row is None or is_never_target(row.odoo_field):
                detail = unmapped.get(name) or "no reviewed facility-profile mapping"
                decisions.append(
                    V2WritebackDecision(
                        cartridge_field=name,
                        odoo_field="",
                        kind="",
                        action=V2_PLAN_SKIP,
                        skip_reason=V2_SKIP_UNMAPPED,
                        detail=detail,
                        evidence_state=entry.state,
                        confidence=entry.confidence,
                    )
                )
                continue
            decisions.append(_decide(row, entry))
    except _Malformed as exc:
        return V2WritebackPlan(spec.key, spec.odoo_model, (), str(exc))
    return V2WritebackPlan(spec.key, spec.odoo_model, tuple(decisions), None)

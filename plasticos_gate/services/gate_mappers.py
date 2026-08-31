"""Typed response mappers for Gate payloads -> Odoo matcher shapes."""

from __future__ import annotations

import re
from typing import Any

from .gate_allowlists import PARTNER_WRITEBACK_FIELD_ALLOWLIST, WEB_LEAD_WRITEBACK_FIELD_MAP
from .gate_contracts import (
    ConvergeResponse,
    MatchCandidate,
    MatchResponse,
    ProcessIntakeResponse,
    ProcessWebLeadResponse,
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
        # CEG hard-gate failures set eligible=false — never surface as selectable matches.
        if cand.get("eligible") is False:
            unresolved.append(
                {
                    "entity_ref": entity_ref,
                    "reason": "candidate not eligible (hard gates failed)",
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
        # Graph publishes "match_direction"; "direction" is the pre-normalisation
        # spelling kept only for the migration window.
        match_direction=payload.get("match_direction") or payload.get("direction"),
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
        results.append(
            {
                "buyer_id": int(item.buyer_partner_id),
                "buyer_name": item.buyer_name,
                "total_score": item.normalized_score if item.normalized_score is not None else 0.0,
                "typical_price": item.typical_price or 0.0,
                "gates_passed": item.gates_passed,
                "gates_failed": item.gates_failed,
                "match_details": item.raw,
                "facility_profile_id": item.facility_profile_id,
                "reason": item.reason,
                "match_source": "gate",
                "gate_packet_id": audit.get("gate_packet_id"),
                "gate_correlation_id": audit.get("gate_correlation_id"),
            }
        )
    results.sort(key=lambda row: row.get("total_score") or 0.0, reverse=True)
    return results


EIE_STATE_COMPLETED = "completed"


def map_converge_response(payload: dict[str, Any]) -> ConvergeResponse:
    """Map an EIE EnrichResponse into Odoo-storable fields WITHOUT fabrication.

    Every EnrichResponse field is carried through (no field loss). Cost is
    ``tokens_used``; ``total_cost_usd`` and ``writeback_applied`` stay
    explicitly UNAVAILABLE (None) — never fabricated (DNB-006). ``status`` is
    derived from EIE ``state``/``failure_reason`` for the Odoo consumer's
    usable-result check.
    """
    # Require an explicit completed state — never manufacture completed/ok on
    # empty, partial, or version-skewed payloads that omit state.
    raw_state = payload.get("state")
    state = raw_state if isinstance(raw_state, str) and raw_state.strip() else None
    failure_reason = payload.get("failure_reason")
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

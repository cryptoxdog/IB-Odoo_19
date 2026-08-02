"""Typed response mappers for Gate payloads -> Odoo matcher shapes."""

from __future__ import annotations

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


def _normalize_score(score: float | None) -> float:
    if score is None:
        return 0.0
    value = float(score)
    if value > 1.0:
        return value / 100.0
    return value


def map_match_response(payload: dict[str, Any]) -> MatchResponse:
    results: list[MatchCandidate] = []
    for item in payload.get("results") or []:
        gates_passed = item.get("gates_passed") or []
        gates_failed = item.get("gates_failed") or []
        if isinstance(gates_passed, int):
            gates_passed = []
        if isinstance(gates_failed, int):
            gates_failed = []
        results.append(
            MatchCandidate(
                buyer_partner_id=item.get("buyer_partner_id") or item.get("buyer_id"),
                buyer_name=item.get("buyer_name"),
                facility_profile_id=item.get("facility_profile_id"),
                score=item.get("score"),
                reason=item.get("reason") or item.get("match_reason"),
                typical_price=item.get("typical_price") or item.get("price_anchor"),
                gates_passed=list(gates_passed),
                gates_failed=list(gates_failed),
                raw=item,
            )
        )
    return MatchResponse(
        status=payload.get("status"),
        match_direction=payload.get("match_direction"),
        top_n=payload.get("top_n"),
        results=results,
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
        results.append(
            {
                "buyer_id": int(item.buyer_partner_id),
                "buyer_name": item.buyer_name,
                "total_score": _normalize_score(item.score),
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


def map_converge_response(payload: dict[str, Any]) -> ConvergeResponse:
    return ConvergeResponse(
        run_id=payload.get("run_id"),
        status=payload.get("status"),
        pass_count=payload.get("pass_count"),
        final_fields=payload.get("final_fields") or {},
        writeback=payload.get("writeback") or {},
        total_tokens=payload.get("total_tokens"),
        total_cost_usd=payload.get("total_cost_usd"),
        raw=payload,
    )


def partner_writeback_from_converge(resp: ConvergeResponse) -> dict[str, Any]:
    writeback = resp.writeback or {}
    partner_fields = writeback.get("partner_fields") if isinstance(writeback, dict) else None
    source = partner_fields if isinstance(partner_fields, dict) and partner_fields else resp.final_fields
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

"""Reference mapper: Odoo <-> EIE converge request/response (TASK-006).

DELIVERABLE for cryptoxdog/IB-Odoo_19 (in scope; apply only when execution
starts). Drop into plasticos_gate and adapt to the Odoo env. Not applied in
the 2026-08-14 remediations pass.

Grounds (verified against EIE app/models/schemas.py + app/engines/handlers.py):
- The constellation "converge" action EIE owns (POST /v1/execute) validates the
  packet payload as EnrichRequest and returns EnrichResponse.
  EnrichRequest : entity(dict, req), object_type(str, req), schema_(alias
    "schema", opt), objective(str, req), kb_context(str|None),
    consensus_threshold(float=0.65), max_variations(int=5, 1..10),
    idempotency_key(str|None)
  EnrichResponse: fields, confidence, kb_content_hash, variation_count,
    consensus_threshold, uncertainty_score, pass_count, inference_version,
    processing_time_ms, enrichment_payload, feature_vector, kb_files_consulted,
    kb_fragment_ids, inferences, quality_tier, grade_matches, tokens_used,
    failure_reason, state
- DNB-006 / Wave 5: EnrichResponse has NO total_cost_usd. Cost is tokens_used.
  Do NOT invent total_cost_usd or a writeback field. Unavailable fields are
  marked explicitly (None), never fabricated.
- The Odoo request historically carried: entity_snapshot, entity_id, domain,
  max_passes. These map into the EIE request; Odoo ids ride in context/metadata,
  NOT as a Gate payload transform.
"""

from __future__ import annotations

from typing import Any

# EIE clamps max_variations to 1..10 (schemas.py). Clamp Odoo's max_passes.
_MIN_VARIATIONS = 1
_MAX_VARIATIONS = 10
_DEFAULT_OBJECTIVE = "Full entity enrichment and inference"


def _clamp_variations(max_passes: Any) -> int:
    try:
        value = int(max_passes)
    except (TypeError, ValueError):
        return 5
    return max(_MIN_VARIATIONS, min(_MAX_VARIATIONS, value))


def build_eie_converge_request(odoo_req: dict[str, Any]) -> dict[str, Any]:
    """Map an Odoo converge request into an EIE EnrichRequest payload.

    odoo_req expected keys (all tolerated-if-missing): entity_snapshot, entity_id,
    domain, max_passes, objective, kb_context, idempotency_key.

    Odoo identifiers (entity_id) are preserved in `entity` context so the response
    can be correlated, but are NOT sent as a top-level Gate transform.
    """
    entity = dict(odoo_req.get("entity_snapshot") or {})
    # Preserve Odoo correlation ids inside the entity context (metadata), not as
    # Gate-level transforms.
    if odoo_req.get("entity_id") is not None:
        entity.setdefault("_odoo_entity_id", odoo_req["entity_id"])

    request: dict[str, Any] = {
        "entity": entity,
        # EIE object_type is required; derive from the Odoo domain/type.
        "object_type": str(odoo_req.get("object_type") or odoo_req.get("domain") or "Account"),
        "objective": str(odoo_req.get("objective") or _DEFAULT_OBJECTIVE),
        "max_variations": _clamp_variations(odoo_req.get("max_passes")),
    }
    # Optional fields — only include when Odoo actually provided them.
    if odoo_req.get("kb_context") is not None:
        request["kb_context"] = str(odoo_req["kb_context"])
    if odoo_req.get("idempotency_key") is not None:
        request["idempotency_key"] = str(odoo_req["idempotency_key"])
    return request


def map_eie_converge_response(eie_resp: dict[str, Any]) -> dict[str, Any]:
    """Map an EIE EnrichResponse into Odoo-storable fields WITHOUT field loss.

    Every EnrichResponse field is carried through. Cost is expressed as
    `tokens_used`; `total_cost_usd` is explicitly UNAVAILABLE (None) — never
    fabricated (DNB-006).
    """
    return {
        # Core enrichment output
        "fields": eie_resp.get("fields", {}),
        "confidence": eie_resp.get("confidence", 0.0),
        "state": eie_resp.get("state", "completed"),
        "failure_reason": eie_resp.get("failure_reason"),
        "quality_tier": eie_resp.get("quality_tier", "unknown"),
        # Convergence telemetry
        "variation_count": eie_resp.get("variation_count", 0),
        "pass_count": eie_resp.get("pass_count", 0),
        "consensus_threshold": eie_resp.get("consensus_threshold", 0.0),
        "uncertainty_score": eie_resp.get("uncertainty_score", 0.0),
        "processing_time_ms": eie_resp.get("processing_time_ms", 0),
        # Provenance / KB lineage
        "inference_version": eie_resp.get("inference_version"),
        "kb_content_hash": eie_resp.get("kb_content_hash", ""),
        "kb_files_consulted": eie_resp.get("kb_files_consulted", []),
        "kb_fragment_ids": eie_resp.get("kb_fragment_ids", []),
        "inferences": eie_resp.get("inferences", []),
        "grade_matches": eie_resp.get("grade_matches", []),
        "enrichment_payload": eie_resp.get("enrichment_payload"),
        "feature_vector": eie_resp.get("feature_vector"),
        # Cost: EIE reports tokens_used only.
        "tokens_used": eie_resp.get("tokens_used", 0),
        # Explicitly UNAVAILABLE — EIE does not return these. Do not fabricate.
        "total_cost_usd": None,  # UNAVAILABLE: EnrichResponse has no cost-in-USD field
        "writeback_applied": None,  # UNAVAILABLE: converge does not perform writeback
    }

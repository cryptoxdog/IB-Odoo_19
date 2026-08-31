"""Typed allowlisted request builders for Gate payloads."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .gate_allowlists import INTAKE_SNAPSHOT_FIELD_MAP, PARTNER_SNAPSHOT_FIELD_MAP, WEB_LEAD_SEED_FIELD_MAP
from .gate_contracts import (
    ConvergeRequest,
    MatchRequest,
    OdooContext,
    ProcessIntakeRequest,
    ProcessWebLeadRequest,
)


def _get_relation_value(record, field_name: str) -> Any:
    if field_name not in record._fields:
        return None
    value = record[field_name]
    if hasattr(value, "id"):
        if field_name == "state_id":
            return getattr(value, "code", None) or getattr(value, "name", None)
        if field_name == "country_id":
            return getattr(value, "code", None) or getattr(value, "name", None)
        return getattr(value, "id", None)
    return value


def build_odoo_context(env, *, model: str, record_id: int) -> OdooContext:
    return OdooContext(
        model=model,
        record_id=record_id,
        company_id=getattr(env.company, "id", None),
        user_id=getattr(env.user, "id", None),
        db_name=getattr(env.cr, "dbname", None),
        correlation_id=f"{model}:{record_id}",
    )


def build_idempotency_key(payload: dict[str, Any], odoo_ctx: dict[str, Any]) -> str | None:
    """Deterministic transport idempotency key for one converge attempt.

    Keyed on the run's stable identity AND a digest of the exact payload, which
    is what makes it correct rather than merely stable:

    * a true replay of one attempt (network retry, double-submitted RPC) sends
      byte-identical payload -> identical key -> Gate may safely dedupe it;
    * ``action_retry_enrichment`` re-runs converge on the SAME run, and
      ``build_converge_request`` re-reads the partner live each time, so a retry
      after the partner was edited is a materially different request. Keying on
      run identity alone would label those the same operation and could replay a
      stale answer for changed input; the digest keeps them distinct.

    Returns None when the run identity is unknown — an unidentifiable request is
    left un-keyed rather than given a guessed one.
    """
    model = odoo_ctx.get("model")
    record_id = odoo_ctx.get("record_id")
    if not model or not record_id:
        return None
    db_name = odoo_ctx.get("db_name") or "db"
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return f"odoo:{db_name}:{model}:{record_id}:{digest}"


_MIN_VARIATIONS = 1
_MAX_VARIATIONS = 10
_DEFAULT_OBJECTIVE = "Full entity enrichment and inference"


def _clamp_variations(max_passes: Any) -> int:
    """EIE clamps max_variations to 1..10; unparseable input falls back to 5."""
    try:
        value = int(max_passes)
    except (TypeError, ValueError):
        return 5
    return max(_MIN_VARIATIONS, min(_MAX_VARIATIONS, value))


def build_converge_request(
    env, run_rec, *, domain: str = "plasticos", max_passes: int | None = None
) -> ConvergeRequest:
    """Map an Odoo enrichment run into an EIE EnrichRequest-shaped request.

    The partner snapshot becomes EIE ``entity``; ``object_type`` derives from
    the Odoo domain; ``max_passes`` maps to clamped ``max_variations``. The
    Odoo entity id is carried on the entity itself (canonical ``id`` plus the
    ``_odoo_entity_id`` compatibility alias), not as a Gate-level transform.
    """
    partner = run_rec.partner_id
    snapshot: dict[str, Any] = {}
    for src_field, payload_field in PARTNER_SNAPSHOT_FIELD_MAP.items():
        value = _get_relation_value(partner, src_field)
        if value not in (None, False, ""):
            snapshot[payload_field] = value
    if getattr(run_rec, "source_ids", False):
        urls = [s.url for s in run_rec.source_ids if getattr(s, "url", None)]
        if urls:
            snapshot["source_urls"] = urls
    odoo = build_odoo_context(env, model=run_rec._name, record_id=run_rec.id).to_dict()
    entity = dict(snapshot)
    # I6 — canonical cross-service identity is ``entity.id``. ``_odoo_entity_id``
    # stays for compatibility with consumers that already read it; both carry
    # the same value, and neither is a new identity scheme.
    entity_id = f"res.partner:{partner.id}"
    entity["id"] = entity_id
    entity["_odoo_entity_id"] = entity_id
    return ConvergeRequest(
        entity=entity,
        object_type=str(domain) if domain else "Account",
        objective=_DEFAULT_OBJECTIVE,
        max_variations=_clamp_variations(max_passes),
        # EIE resolves the KB domain from `domain_id` -> `domain` -> `kb_context`
        # -> `object_type`. Leaving this unset made the domain resolve only
        # because `object_type` happens to carry it, which is the last fallback
        # and coincidence rather than contract. `kb_context` is the
        # EnrichRequest field for exactly this, so state it.
        kb_context=str(domain) if domain else None,
        odoo=odoo,
    )


def build_match_request(env, *, intake=None, supplier=None, top_n: int = 20, mode: str = "strict") -> MatchRequest:
    query: dict[str, Any] = {}
    odoo: dict[str, Any] = {}
    if intake is not None:
        if "polymer_id" in intake._fields and intake.polymer_id:
            query["polymer_type"] = intake.polymer_id.code or intake.polymer_id.name
        if "form_id" in intake._fields and intake.form_id:
            query["form"] = intake.form_id.code or intake.form_id.name
        if "color_id" in intake._fields and intake.color_id:
            query["color"] = intake.color_id.code or intake.color_id.name
        for src, dst in INTAKE_SNAPSHOT_FIELD_MAP.items():
            value = _get_relation_value(intake, src)
            if value not in (None, False, ""):
                query[dst] = value
        if "source_type_id" in intake._fields and intake.source_type_id:
            query["source_type"] = intake.source_type_id.code or intake.source_type_id.name
        odoo = build_odoo_context(env, model=intake._name, record_id=intake.id).to_dict()
        query["intake_id"] = intake.id
        if getattr(intake, "partner_id", False):
            query["supplier_partner_id"] = intake.partner_id.id
    elif supplier is not None:
        odoo = build_odoo_context(env, model=supplier._name, record_id=supplier.id).to_dict()
        query["supplier_partner_id"] = supplier.id
    else:
        raise ValueError("build_match_request requires intake or supplier")
    if mode:
        query["mode"] = mode
    return MatchRequest(query=query, top_n=top_n, odoo=odoo)


def build_web_lead_request(env, lead_rec, *, raw_payload: dict[str, Any] | None = None) -> ProcessWebLeadRequest:
    seed: dict[str, Any] = {}
    for src_field, payload_field in WEB_LEAD_SEED_FIELD_MAP.items():
        if src_field in lead_rec._fields:
            value = lead_rec[src_field]
            if value not in (None, False, ""):
                seed[payload_field] = value
    images = lead_rec.image_urls if "image_urls" in lead_rec._fields and lead_rec.image_urls else []
    if images:
        seed["image_urls"] = images
    odoo = build_odoo_context(env, model=lead_rec._name, record_id=lead_rec.id).to_dict()
    return ProcessWebLeadRequest(
        lead_id=lead_rec.lead_id,
        domain="plasticos",
        source=lead_rec.source or "cognito_form",
        raw_payload=raw_payload or (lead_rec.raw_payload or {}),
        normalized_seed=seed,
        odoo=odoo,
    )


def build_intake_request(env, intake_rec) -> ProcessIntakeRequest:
    snapshot: dict[str, Any] = {}
    if "partner_id" in intake_rec._fields and intake_rec.partner_id:
        snapshot["supplier_partner_id"] = intake_rec.partner_id.id
    if "polymer_id" in intake_rec._fields and intake_rec.polymer_id:
        snapshot["polymer_type"] = intake_rec.polymer_id.code or intake_rec.polymer_id.name
    if "form_id" in intake_rec._fields and intake_rec.form_id:
        snapshot["form"] = intake_rec.form_id.code or intake_rec.form_id.name
    if "color_id" in intake_rec._fields and intake_rec.color_id:
        snapshot["color"] = intake_rec.color_id.code or intake_rec.color_id.name
    for src, dst in INTAKE_SNAPSHOT_FIELD_MAP.items():
        value = _get_relation_value(intake_rec, src)
        if value not in (None, False, ""):
            snapshot[dst] = value
    odoo = build_odoo_context(env, model=intake_rec._name, record_id=intake_rec.id).to_dict()
    return ProcessIntakeRequest(intake_id=intake_rec.id, domain="plasticos", intake_snapshot=snapshot, odoo=odoo)

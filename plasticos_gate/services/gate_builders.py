"""Typed allowlisted request builders for Gate payloads."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .gate_allowlists import INTAKE_SNAPSHOT_FIELD_MAP, PARTNER_SNAPSHOT_FIELD_MAP, WEB_LEAD_SEED_FIELD_MAP
from .gate_contracts import (
    MATCH_DIRECTION_SUPPLY_TO_BUYER,
    ConvergeRequest,
    MatchRequest,
    OdooContext,
    ProcessIntakeRequest,
    ProcessWebLeadRequest,
    normalize_match_direction,
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


_MIN_VARIATIONS = 1
_MAX_VARIATIONS = 10
_DEFAULT_OBJECTIVE = "Full entity enrichment and inference"

#: EIE resolves entity identity from ``entity["id"]``. This is the canonical key.
ENTITY_ID_KEY = "id"
#: Dual-populated for one migration window while EIE consumers still read it.
#: Remove only after telemetry proves every consumer reads ``entity["id"]``.
LEGACY_ENTITY_ID_KEY = "_odoo_entity_id"

#: Bumped deliberately when the converge input contract or pipeline policy
#: changes in a way that must invalidate previously cached results.
CONVERGE_PIPELINE_CONTRACT_VERSION = "v1"
CONVERGE_ACTION_SLUG = "converge"

PARTNER_MODEL = "res.partner"
# Named rather than inline: the phantom-enum AST scan treats bare string
# literals in comparisons as candidate enum values (same reason gate_config
# builds its dict keys from names).
SOURCE_URLS_KEY = "source_urls"


def build_entity_ref(model: str, record_id: int) -> str:
    """Return the canonical constellation entity ref ``"<model>:<id>"``."""
    return f"{model}:{record_id}"


def _canonical_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministically ordered snapshot with normalised source URLs.

    ``source_urls`` is deduplicated and sorted so that ordering noise from the
    Odoo relation never changes the fingerprint. Values are otherwise carried
    through unchanged — normalisation must not silently alter enrichment input.
    """
    canonical: dict[str, Any] = {}
    for key in sorted(snapshot):
        value = snapshot[key]
        if key == SOURCE_URLS_KEY and isinstance(value, (list, tuple, set)):
            canonical[key] = sorted({str(url) for url in value})
        else:
            canonical[key] = value
    return canonical


def converge_input_fingerprint(
    snapshot: dict[str, Any],
    *,
    object_type: str,
    objective: str,
    max_variations: int,
    pipeline_version: str = CONVERGE_PIPELINE_CONTRACT_VERSION,
) -> str:
    """Hash the semantic enrichment inputs — and only those.

    Deliberately excludes run id, packet id, attempt number, and any timestamp:
    a retry of the same semantic work must produce the same fingerprint, while a
    changed partner snapshot, changed source URLs, or a deliberate pipeline
    contract bump must produce a different one.
    """
    material = {
        "snapshot": _canonical_snapshot(snapshot),
        "object_type": object_type,
        "objective": objective,
        "max_variations": max_variations,
        "pipeline_version": pipeline_version,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_converge_idempotency_key(
    *,
    db_name: str | None,
    entity_ref: str,
    fingerprint: str,
    pipeline_version: str = CONVERGE_PIPELINE_CONTRACT_VERSION,
) -> str:
    """Build the durable converge idempotency key.

    Shape: ``odoo:<db>:<entity_ref>:converge:<pipeline_version>:<fingerprint>``.
    """
    db = (db_name or "unknown").strip() or "unknown"
    return f"odoo:{db}:{entity_ref}:{CONVERGE_ACTION_SLUG}:{pipeline_version}:{fingerprint}"


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
    the Odoo domain; ``max_passes`` maps to clamped ``max_variations``.

    Identity is canonical: ``entity["id"]`` carries ``"res.partner:<id>"``,
    which is the key EIE resolves entity identity from. ``_odoo_entity_id`` is
    dual-populated for one migration window. The request also carries a
    deterministic ``idempotency_key`` derived only from semantic inputs, so a
    retry of the same work reuses the cached computation instead of paying for
    it again.
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
            snapshot[SOURCE_URLS_KEY] = urls

    odoo = build_odoo_context(env, model=run_rec._name, record_id=run_rec.id).to_dict()
    object_type = str(domain) if domain else "Account"
    max_variations = _clamp_variations(max_passes)

    # Fingerprint the snapshot BEFORE identity keys are injected: identity is
    # already carried separately in the key, and mixing it in would couple the
    # semantic hash to the identity encoding.
    fingerprint = converge_input_fingerprint(
        snapshot,
        object_type=object_type,
        objective=_DEFAULT_OBJECTIVE,
        max_variations=max_variations,
    )
    entity_ref = build_entity_ref(PARTNER_MODEL, partner.id)
    idempotency_key = build_converge_idempotency_key(
        db_name=odoo.get("db_name"),
        entity_ref=entity_ref,
        fingerprint=fingerprint,
    )

    entity = dict(snapshot)
    entity[ENTITY_ID_KEY] = entity_ref
    entity.setdefault(LEGACY_ENTITY_ID_KEY, entity_ref)
    return ConvergeRequest(
        entity=entity,
        object_type=object_type,
        objective=_DEFAULT_OBJECTIVE,
        max_variations=max_variations,
        idempotency_key=idempotency_key,
        odoo=odoo,
    )


def build_match_request(
    env,
    *,
    intake=None,
    supplier=None,
    top_n: int = 20,
    mode: str = "strict",
    match_direction: str = MATCH_DIRECTION_SUPPLY_TO_BUYER,
) -> MatchRequest:
    """Build a Graph match request.

    An Odoo intake (or a bare supplier) is a supply opportunity looking for a
    buyer facility, so the direction is ``supply_opportunity_to_buyer_facility``
    — one of the two directions PlasticOS Graph actually recognises. The Odoo
    -local ``intake_to_buyer`` spelling is normalised, never forwarded.
    """
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
    return MatchRequest(
        query=query,
        match_direction=normalize_match_direction(match_direction),
        top_n=top_n,
        odoo=odoo,
    )


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

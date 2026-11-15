"""Typed allowlisted request builders for Gate payloads."""

from __future__ import annotations

from typing import Any

from .gate_allowlists import (
    INTAKE_SNAPSHOT_FIELD_MAP,
    PARTNER_SNAPSHOT_FIELD_MAP,
    PARTNER_WRITEBACK_FIELD_ALLOWLIST,
    V2_KIND_BOOLEAN,
    V2_KIND_MANY2MANY_CODE,
    V2_KIND_MANY2ONE_CODE,
    V2_NUMERIC_KINDS,
    V2_TARGET_FACILITY_PROFILE,
    WEB_LEAD_SEED_FIELD_MAP,
    ConvergeV2FieldRow,
    resolve_v2_target,
)
from .gate_config import gate_consensus_threshold
from .gate_contracts import (
    CartridgePin,
    ConvergeRequest,
    ConvergeRequestV2,
    MatchRequest,
    OdooContext,
    ProcessIntakeRequest,
    ProcessWebLeadRequest,
    freeze,
    thaw,
)
from .gate_sweep import SweepCandidate


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


# Operation-identity family for enrichment converge runs. The family plus the
# database, model and record id fully name one durable Odoo execution.
ENRICHMENT_OPERATION_FAMILY = "enrichment"


def build_operation_id(
    odoo_ctx: dict[str, Any], *, family: str = ENRICHMENT_OPERATION_FAMILY, attempt: int = 1
) -> str | None:
    """One stable logical operation identity for a durable Odoo run (ADR-006).

    Semantic form ``odoo:<family>:<db>:<model>:<record-id>`` for the first
    attempt and ``odoo:<family>:<db>:<model>:<record-id>:attempt-<n>`` for an
    operator retry. The database, model and record id are the scoping that
    makes the ADR's preferred ``odoo:enrichment:<durable-run-id>`` form
    unambiguous across databases.

    ``attempt`` exists because Gate caches the response to a logical operation
    under this identity — including an EIE domain failure (``state="failed"``).
    An operator retry that reused the identity received the cached failure for
    the lifetime of the Gate process and could never reach EIE again. A retry
    is the business act meaning "ask again", so it is a new logical operation:
    same durable run, new attempt number, new identity.

    Generated ONCE per attempt and reused at both replay boundaries: the
    EnrichRequest domain idempotency field and the TransportPacket header.
    Those remain different mechanisms owned by EIE and Gate_SDK respectively —
    they share a logical identity, they do not become one subsystem.

    Identity is derived only from durable run identity and the attempt
    counter. It carries no payload digest, timestamp, or randomness, so:

    * the same attempt of the same durable run always yields the same id, so a
      transport replay of that attempt is recognised as the same operation;
    * an operator retry (``gate_attempt`` + 1) yields a new id (ADR-006
      amendment 2026-11-08);
    * a new run over the same partner yields a different id;
    * a different partner yields a different id.

    A previous implementation mixed a SHA-256 digest of the serialized payload
    into the key. That made a retry of one run after the partner was edited a
    *different* logical operation, which is ADR-006's rejected Option B: it
    makes "same operation" a serialization fact rather than a business fact,
    and leaves the transport key uncorrelatable with the durable run. Asking
    again is a business act: an operator retry or a new run, never a payload
    edit.

    Returns None when run identity is unknown; an unidentifiable request is left
    un-keyed rather than given a guessed identity.
    """
    model = odoo_ctx.get("model")
    record_id = odoo_ctx.get("record_id")
    if not model or not record_id:
        return None
    db_name = odoo_ctx.get("db_name") or "db"
    base = f"odoo:{family}:{db_name}:{model}:{record_id}"
    try:
        attempt_no = int(attempt)
    except (TypeError, ValueError):
        attempt_no = 1
    if attempt_no > 1:
        return f"{base}:attempt-{attempt_no}"
    return base


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
    env,
    run_rec,
    *,
    domain: str = "plasticos",
    max_passes: int | None = None,
    schema: dict[str, str] | None = None,
    field_thresholds: dict[str, float] | None = None,
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
        consensus_threshold=gate_consensus_threshold(env),
        field_thresholds=field_thresholds,
        # EIE resolves the KB domain from `domain_id` -> `domain` -> `kb_context`
        # -> `object_type`. Leaving this unset made the domain resolve only
        # because `object_type` happens to carry it, which is the last fallback
        # and coincidence rather than contract. `kb_context` is the
        # EnrichRequest field for exactly this, so state it.
        kb_context=str(domain) if domain else None,
        # Ask EIE for exactly the partner fields Odoo is allowed to write back
        # (the writeback allowlist); "string" is EIE's canonical type token.
        schema=schema or dict.fromkeys(sorted(PARTNER_WRITEBACK_FIELD_ALLOWLIST), "string"),
        # ADR-006: generated once here and carried on the request, so the caller
        # hands the SAME logical value to the transport header rather than
        # deriving a second, unrelated one. EnrichRequest.idempotency_key is a
        # canonical EIE field, so this is domain propagation, not a new dialect.
        # The run's attempt counter makes an operator retry a new operation.
        idempotency_key=build_operation_id(odoo, attempt=_run_attempt(run_rec)),
        odoo=odoo,
    )


# ── Converge request v2 ────────────────────────────────────────────────────

# Partner role-tag codes that name a commercial role the cartridge declares.
V2_ROLE_TAG_CODES = ("supplier", "buyer")
V2_OBSERVATION_SOURCE_KIND = "odoo_record"


class ConvergeV2NothingToRequest(ValueError):
    """Every mapped Odoo field of the target already holds a value."""


def derive_subject_role(partner) -> str | None:
    """The partner's own commercial role, only when its role tags make it unambiguous.

    Reads the partner's own ``company_role_tag_ids`` codes. Exactly one of
    ``supplier`` / ``buyer`` gives that role; none or both gives None, and the
    request then carries no role rather than a guessed one.
    """
    if "company_role_tag_ids" not in getattr(partner, "_fields", {}):
        return None
    codes = {getattr(tag, "code", None) for tag in partner.company_role_tag_ids}
    roles = [code for code in V2_ROLE_TAG_CODES if code in codes]
    return roles[0] if len(roles) == 1 else None


def odoo_value_for_row(record, row: ConvergeV2FieldRow) -> Any:
    """The record's current value for a mapped field, as the cartridge would state it.

    None means empty. For numeric fields 0 is empty (Odoo cannot tell an unset
    float from 0.0), the same rule merge-not-overwrite applies at write time.
    """
    if row.odoo_field not in getattr(record, "_fields", {}):
        return None
    value = record[row.odoo_field]
    if row.kind == V2_KIND_MANY2ONE_CODE:
        code = getattr(value, row.code_field, None) if value else None
        return code or None
    if row.kind == V2_KIND_MANY2MANY_CODE:
        codes = [getattr(rec, row.code_field, None) for rec in value] if value else []
        codes = [code for code in codes if code]
        if not codes:
            return None
        if row.code_item_key:
            return [{row.code_item_key: code} for code in codes]
        return codes
    if row.kind == V2_KIND_BOOLEAN:
        return bool(value)
    if value in (None, False, ""):
        return None
    if row.kind in V2_NUMERIC_KINDS and not value:
        return None
    return value


def _row_canonical_unit(row: ConvergeV2FieldRow) -> str | None:
    """The unit an Odoo numeric value is stored in: the row's factor-1 unit."""
    return next((unit for unit, factor in row.units.items() if factor == 1.0), None)


def build_converge_request_v2(
    env,
    run_rec,
    *,
    target: str,
    record,
    cartridge: CartridgePin,
    max_passes: int | None = None,
    field_defs=None,
    subject: str | None = None,
) -> ConvergeRequestV2:
    """Build a converge request v2 for one partner, material profile or facility profile.

    ``targets`` are the mapping-table rows whose Odoo field is empty on
    ``record``; ``observations`` are the rows whose Odoo field already holds a
    value, offered as evidence only. The entity stays ``res.partner:<id>`` of
    the run's partner (gate-integration ADR-005); the engine never mints one.

    The facility profile has no fixed table: pass the model's field
    definitions (``field_defs``, a sequence of ``OdooFieldDef``) and the target
    is derived from them (operator decision 2026-11-13), one subject per
    request: ``subject`` defaults to ``material``; ``facility`` asks the
    same-named contact/capacity fields.

    Raises ConvergeV2NothingToRequest when no mapped field is empty, and
    KeyError for a target the table does not declare.
    """
    spec = resolve_v2_target(target, field_defs, subject=subject, version=cartridge.version)
    partner = run_rec.partner_id
    odoo = build_odoo_context(env, model=run_rec._name, record_id=run_rec.id).to_dict()
    return _assemble_converge_request_v2(
        env,
        spec=spec,
        record=record,
        partner=partner,
        cartridge=cartridge,
        odoo=odoo,
        idempotency_key=build_operation_id(odoo, attempt=_run_attempt(run_rec)),
        max_passes=max_passes,
    )


def _assemble_converge_request_v2(
    env,
    *,
    spec,
    record,
    partner,
    cartridge: CartridgePin,
    odoo: dict[str, Any],
    idempotency_key: str | None,
    max_passes: int | None = None,
) -> ConvergeRequestV2:
    """The shared converge v2 body: interactive runs and the scheduled sweep build it here."""
    if getattr(record, "_name", None) != spec.odoo_model:
        raise ValueError(f"target {spec.key!r} enriches {spec.odoo_model}, not {getattr(record, '_name', None)}")
    if spec.odoo_model == "res.partner":
        owner = record
    else:
        owner = getattr(record, "partner_id", None)
        if not owner:
            raise ValueError(f"{spec.odoo_model}:{record.id} has no partner (lead-owned) and cannot be enriched")
    if not partner or getattr(owner, "id", None) != partner.id:
        raise ValueError(
            f"{spec.odoo_model}:{record.id} does not belong to the run partner res.partner:{getattr(partner, 'id', None)}"
        )
    record_ref = f"{spec.odoo_model}:{record.id}"
    targets = []
    observations = []
    for row in spec.rows:
        current = odoo_value_for_row(record, row)
        if current is None:
            targets.append({"field": row.cartridge_field, "type": row.request_type()})
            continue
        observation = {
            "field": row.cartridge_field,
            "value": current,
            "source_kind": V2_OBSERVATION_SOURCE_KIND,
            "source_ref": f"{record_ref}#{row.odoo_field}",
        }
        if row.kind in V2_NUMERIC_KINDS:
            unit = _row_canonical_unit(row)
            if unit:
                observation["unit"] = unit
        observations.append(observation)
    if not targets:
        raise ConvergeV2NothingToRequest(f"{record_ref}: every mapped field already holds a value")

    entity: dict[str, Any] = {}
    for src_field, payload_field in PARTNER_SNAPSHOT_FIELD_MAP.items():
        value = _get_relation_value(partner, src_field)
        if value not in (None, False, ""):
            entity[payload_field] = value
    entity_id = f"res.partner:{partner.id}"
    entity["id"] = entity_id
    entity["_odoo_entity_id"] = entity_id
    odoo = dict(odoo)
    odoo["target_model"] = spec.odoo_model
    odoo["target_res_id"] = record.id
    return ConvergeRequestV2(
        cartridge=cartridge,
        node=spec.node,
        subject_type=spec.subject_type,
        subject_role=derive_subject_role(partner),
        targets=freeze(targets),
        observations=freeze(observations),
        entity=freeze(entity),
        object_type="res.partner",
        objective=_DEFAULT_OBJECTIVE,
        max_variations=_clamp_variations(max_passes),
        consensus_threshold=gate_consensus_threshold(env),
        idempotency_key=idempotency_key,
        odoo=freeze(odoo),
    )


SWEEP_OPERATION_FAMILY = "enrichment-sweep"


def build_facility_sweep_request_v2(
    env,
    sweep_rec,
    *,
    record,
    cartridge: CartridgePin,
    field_defs,
    subject: str | None = None,
) -> ConvergeRequestV2:
    """The converge v2 request one sweep candidate stands for (scheduled sweep, ADR-012 2026-11-15).

    Same rows, targets and observations as an interactive facility-profile run
    (``_assemble_converge_request_v2``); the partner is the profile's own and the
    Odoo context names the sweep record, so the reply is parsed against exactly
    what Odoo asked. Raises ConvergeV2NothingToRequest when nothing is empty.
    """
    spec = resolve_v2_target(V2_TARGET_FACILITY_PROFILE, field_defs, subject=subject, version=cartridge.version)
    odoo = build_odoo_context(env, model=sweep_rec._name, record_id=sweep_rec.id).to_dict()
    odoo["target_partner_id"] = record.partner_id.id
    return _assemble_converge_request_v2(
        env,
        spec=spec,
        record=record,
        partner=record.partner_id,
        cartridge=cartridge,
        odoo=odoo,
        idempotency_key=f"{build_operation_id(odoo, family=SWEEP_OPERATION_FAMILY)}:res.partner:{record.partner_id.id}",
    )


def build_sweep_candidate(request: ConvergeRequestV2) -> SweepCandidate:
    """The candidate EIE receives: the request's current values in cartridge field names."""
    entity = {obs["field"]: thaw(obs["value"]) for obs in request.observations}
    return SweepCandidate(entity_id=request.entity["id"], entity=entity, node_label=request.node)


def _run_attempt(run_rec) -> int:
    """Read the run's Gate attempt counter; absent or malformed means attempt 1."""
    try:
        value = int(getattr(run_rec, "gate_attempt", 1) or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, value)


# Frozen-lot snapshot keys that may cross into the Gate match query. The lot is
# minted by CRM Bridge from an approved Material Profile; facility and intake
# keys are present only when that evidence exists, so nothing here fabricates.
LOT_SNAPSHOT_QUERY_KEYS = (
    "polymer_type",
    "form",
    "color",
    "source_type",
    "material_grade",
    "packaging_type",
    "filler_type",
    "quantity_per_load_lbs",
    "contamination_pct",
    "mfi",
    "lat",
    "lon",
    "supplier_partner_id",
    "material_profile_id",
    "facility_profile_id",
    "facility_partner_id",
    "intake_id",
)


def _color_query_value(record):
    """One named color stays a string. Several become a list. None omits the key."""
    if "color_ids" not in record._fields:
        return None
    named = []
    for color in record.color_ids:
        label = color.code or color.name
        if label:
            named.append(label)
    if len(named) == 1:
        return named[0]
    if named:
        return named
    return None


def build_match_request(
    env,
    *,
    intake=None,
    supplier=None,
    match_run=None,
    snapshot: dict[str, Any] | None = None,
    top_n: int = 20,
    mode: str = "strict",
) -> MatchRequest:
    query: dict[str, Any] = {}
    odoo: dict[str, Any] = {}
    if snapshot is not None:
        if match_run is None:
            raise ValueError("build_match_request with a frozen snapshot requires the match_run it is for")
        for key in LOT_SNAPSHOT_QUERY_KEYS:
            value = snapshot.get(key)
            if value not in (None, False, ""):
                query[key] = value
        if not query.get("supplier_partner_id"):
            raise ValueError("frozen lot snapshot has no supplier_partner_id")
        odoo = build_odoo_context(env, model=match_run._name, record_id=match_run.id).to_dict()
    elif intake is not None:
        if "polymer_id" in intake._fields and intake.polymer_id:
            query["polymer_type"] = intake.polymer_id.code or intake.polymer_id.name
        if "form_id" in intake._fields and intake.form_id:
            query["form"] = intake.form_id.code or intake.form_id.name
        color_value = _color_query_value(intake)
        if color_value is not None:
            query["color"] = color_value
        for src, dst in INTAKE_SNAPSHOT_FIELD_MAP.items():
            value = _get_relation_value(intake, src)
            if value not in (None, False, ""):
                query[dst] = value
        if "source_type_id" in intake._fields and intake.source_type_id:
            query["source_type"] = intake.source_type_id.code or intake.source_type_id.name
        context_record = match_run or intake
        odoo = build_odoo_context(
            env,
            model=context_record._name,
            record_id=context_record.id,
        ).to_dict()
        query["intake_id"] = intake.id
        if getattr(intake, "partner_id", False):
            query["supplier_partner_id"] = intake.partner_id.id
    elif supplier is not None:
        odoo = build_odoo_context(env, model=supplier._name, record_id=supplier.id).to_dict()
        query["supplier_partner_id"] = supplier.id
    else:
        raise ValueError("build_match_request requires a frozen snapshot, an intake, or a supplier")
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
    color_value = _color_query_value(intake_rec)
    if color_value is not None:
        snapshot["color"] = color_value
    for src, dst in INTAKE_SNAPSHOT_FIELD_MAP.items():
        value = _get_relation_value(intake_rec, src)
        if value not in (None, False, ""):
            snapshot[dst] = value
    odoo = build_odoo_context(env, model=intake_rec._name, record_id=intake_rec.id).to_dict()
    return ProcessIntakeRequest(intake_id=intake_rec.id, domain="plasticos", intake_snapshot=snapshot, odoo=odoo)

"""Converge contract v2 codec: request builder, response parser, writeback plan.

Contract authority (read-only): Quantum-L9/Enrichment.Inference.Engine at
``8c02aa9`` (contract text unchanged since ``b1b295a``) — ``docs/contracts/converge/request.v2.md`` and ``response.v2.md``
(both FROZEN 2026-11-13, including Revision 1) and ``domains/plasticos/spec.yaml``
(cartridge plasticos 0.5.0, ``subjects`` block). These tests are pure Python:
no Odoo runtime, no Gate, no network.

v1 is the default and must stay byte-for-byte what it was; the last section
pins that.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services import gate_allowlists as allow  # noqa: E402
from plasticos_gate.services.gate_builders import (  # noqa: E402
    ConvergeV2NothingToRequest,
    build_converge_request,
    build_converge_request_v2,
    derive_subject_role,
)
from plasticos_gate.services.gate_config import (  # noqa: E402
    CONVERGE_CONTRACT_V1,
    CONVERGE_CONTRACT_V2,
    GateIntegrationError,
    resolve_converge_contract,
)
from plasticos_gate.services.gate_contracts import (  # noqa: E402
    CONVERGE_REQUEST_V2,
    CONVERGE_RESPONSE_V2,
    CartridgePin,
)
from plasticos_gate.services.gate_mappers import (  # noqa: E402
    V2_PLAN_SKIP,
    V2_PLAN_WRITE,
    V2_REJECT_MALFORMED,
    V2_REJECT_MISSING_ENTRY,
    V2_REJECT_NOT_COMPLETED,
    V2_REJECT_RESOLUTION,
    V2_REJECT_UNSUPPORTED_CONTRACT,
    V2_REJECT_V1_REPLY,
    V2_SKIP_CONFLICTING,
    V2_SKIP_NOT_ADMITTED,
    V2_SKIP_UNIT,
    V2_SKIP_UNKNOWN,
    map_converge_response,
    parse_converge_response_v2,
    partner_writeback_from_converge,
    plan_converge_v2_writeback,
)

FIXTURES = ROOT / "tests" / "fixtures" / "gate_converge_v2"
PIN = CartridgePin("plasticos", "0.5.0")

# The plasticos 0.5.0 cartridge (EIE domains/plasticos/spec.yaml @ 8c02aa9):
# node Facility, its declared property types, and the subject vocabulary.
CARTRIDGE_NODE = "Facility"
CARTRIDGE_DECLARATIONS = {
    "facility_id": {"type": "string"},
    "name": {"type": "string"},
    "min_density": {"type": "float"},
    "max_density": {"type": "float"},
    "min_mfi": {"type": "float"},
    "max_mfi": {"type": "float"},
    "contamination_tolerance": {"type": "float"},
    "capacity_tons_month": {"type": "float"},
    "tier": {"type": "string"},
    "processed_polymers": {
        "type": "list",
        "items": {"type": "map", "properties": [{"name": "code", "type": "string", "required": True}]},
    },
    "city": {"type": "string"},
    "state": {"type": "string"},
    "zip_code": {"type": "string"},
    "material_grade": {"type": "string"},
    "certifications": {"type": "list", "items": {"type": "string"}},
    "street": {"type": "string"},
    "street2": {"type": "string"},
    "website": {"type": "string"},
    "email": {"type": "string"},
    "phone": {"type": "string"},
    "material_forms": {"type": "list", "items": {"type": "string"}},
}
CARTRIDGE_SUBJECTS = {
    "facility": {
        "name",
        "city",
        "state",
        "zip_code",
        "street",
        "street2",
        "website",
        "email",
        "phone",
        "capacity_tons_month",
        "tier",
    },
    "material": {
        "processed_polymers",
        "min_density",
        "max_density",
        "min_mfi",
        "max_mfi",
        "contamination_tolerance",
        "material_grade",
        "material_forms",
        "certifications",
    },
}
CARTRIDGE_ROLES = {"supplier", "buyer"}
# request.v2.md sections 3 and 9: every top-level member a v2 body may carry.
REQUEST_V2_MEMBERS = {
    "contract",
    "cartridge",
    "node",
    "subject",
    "targets",
    "observations",
    "entity",
    "entity_id",
    "object_type",
    "objective",
    "consensus_threshold",
    "max_variations",
    "max_passes",
    "idempotency_key",
    "odoo",
}


# ── Fakes (duck-typed Odoo records) ─────────────────────────────────────────


class _Rec:
    """Minimal record: ``_name``, ``_fields``, ``id`` and item access."""

    def __init__(self, model: str, rec_id: int, /, **values):
        self._name = model
        self.id = rec_id
        self._values = values
        self._fields = dict.fromkeys(values)

    def __getitem__(self, key):
        return self._values[key]

    def __getattr__(self, key):
        try:
            return self.__dict__["_values"][key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __bool__(self):
        return True


class _Coded:
    def __init__(self, code: str):
        self.code = code
        self.name = code

    def __bool__(self):
        return True


class _Env:
    def __init__(self, params: dict | None = None):
        self.company = type("C", (), {"id": 1})()
        self.user = type("U", (), {"id": 2})()
        self.cr = type("R", (), {"dbname": "plasticos"})()
        self._params = params or {}

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        params = self._params

        class _ICP:
            def sudo(self):
                return self

            def get_param(self, key, default=None):
                return params.get(key, default)

        return _ICP()


def _partner(pid: int, *, roles=(), **values):
    base = {
        "name": False,
        "website": False,
        "city": False,
        "zip": False,
        "street": False,
        "street2": False,
        "comment": False,
        "email": False,
        "phone": False,
        "state_id": False,
        "country_id": _Coded("US"),
        "company_role_tag_ids": [_Coded(code) for code in roles],
    }
    base.update(values)
    return _Rec("res.partner", pid, **base)


def _run(run_id: int, partner):
    return _Rec("plasticos.enrichment.run", run_id, partner_id=partner, source_ids=(), gate_attempt=1)


def _partner_case():
    partner = _partner(
        55,
        roles=("supplier",),
        name="Acme Recycling",
        street="1 Main St",
        email="ops@acme.example",
        phone="+1 704 555 0100",
    )
    return partner, _run(7, partner), partner


def _supplier_facility_case():
    partner = _partner(56, roles=("supplier",), name="Polymer Supply Co")
    profile = _Rec(
        "plasticos.facility.profile",
        402,
        partner_id=partner,
        accepted_polymer_ids=[],
        density_min=0.0,
        density_max=0.0,
        melt_index_min=0.0,
        melt_index_max=0.0,
        contamination_tolerance_pct=0.0,
        capacity_lbs_month=0,
    )
    return partner, _run(8, partner), profile


SUPPLIER_FACILITY = "supplier_facility"


def _facility_case():
    partner = _partner(57, roles=("buyer",), name="Buyer Plant")
    profile = _Rec(
        "plasticos.facility.profile",
        401,
        partner_id=partner,
        accepted_polymer_ids=[],
        density_min=0.0,
        density_max=0.965,
        melt_index_min=0.2,
        melt_index_max=8.0,
        contamination_tolerance_pct=0.0,
        capacity_lbs_month=50000,
    )
    return partner, _run(9, partner), profile


def _fd(name, ftype, **kw):
    return allow.OdooFieldDef(name, ftype, **kw)


# plasticos.facility.profile as its field definitions say (plasticos_facility_profile
# + plasticos_crm_bridge at Staging 26211b5), the shape the Odoo caller passes in.
FACILITY_FIELD_DEFS = (
    _fd("id", "integer", readonly=True),
    _fd("display_name", "char", stored=False, computed=True),
    _fd("create_uid", "many2one", relation="res.users", readonly=True),
    _fd("partner_id", "many2one", relation="res.partner"),
    _fd("crm_lead_id", "many2one", relation="crm.lead"),
    _fd("active", "boolean"),
    _fd("associated_lead_ids", "one2many", relation="crm.lead", stored=False),
    _fd("material_profile_ids", "one2many", relation="plasticos.material.profile", stored=False),
    _fd("message_ids", "one2many", relation="mail.message", stored=False),
    _fd("message_partner_ids", "many2many", relation="res.partner", computed=True),
    _fd("avg_truckload_lbs", "float"),
    _fd("iso_certified", "boolean"),
    _fd("food_grade_certified", "boolean"),
    _fd("min_lot_size_lbs", "float"),
    _fd("freeform_notes", "text"),
    _fd("contamination_tolerance_pct", "float"),
    _fd("moisture_tolerance_pct", "float"),
    _fd("capacity_lbs_month", "integer"),
    _fd("application_notes", "text"),
    _fd("embedding_ready", "boolean", computed=True),
)


# Case name -> (fixture factory, reply fixture, converge target). The partner
# and facility-profile targets are the only two (CTO directive 2026-11-13:
# the `material` subject is a facility's capability, never one material profile).
CASES = {
    allow.V2_TARGET_PARTNER: (_partner_case, "response_partner.json", allow.V2_TARGET_PARTNER),
    allow.V2_TARGET_FACILITY_PROFILE: (
        _facility_case,
        "response_facility_profile.json",
        allow.V2_TARGET_FACILITY_PROFILE,
    ),
    SUPPLIER_FACILITY: (
        _supplier_facility_case,
        "response_supplier_facility_profile.json",
        allow.V2_TARGET_FACILITY_PROFILE,
    ),
}


def _target(case):
    return CASES[case][2] if case in CASES else case


def _defs(case):
    return FACILITY_FIELD_DEFS if _target(case) == allow.V2_TARGET_FACILITY_PROFILE else None


def _spec(case):
    return allow.resolve_v2_target(_target(case), _defs(case))


def _request(case: str, pin: CartridgePin = PIN):
    _partner_rec, run, record = CASES[case][0]()
    return build_converge_request_v2(
        _Env(), run, target=_target(case), record=record, cartridge=pin, field_defs=_defs(case)
    )


def _reply(case: str) -> dict:
    return json.loads((FIXTURES / CASES[case][1]).read_text())


def _parse(target: str, reply: dict | None = None):
    request = _request(target)
    return request, parse_converge_response_v2(reply if reply is not None else _reply(target), request=request)


# ── Mapping table vs the cartridge ──────────────────────────────────────────


@pytest.mark.parametrize("target", sorted(CASES))
def test_every_row_is_a_declared_node_field_with_the_cartridge_type(target):
    spec = _spec(target)
    assert spec.node == CARTRIDGE_NODE
    assert spec.subject_type in CARTRIDGE_SUBJECTS
    for row in spec.rows:
        assert row.cartridge_field in CARTRIDGE_DECLARATIONS, row
        assert row.declaration_dict() == CARTRIDGE_DECLARATIONS[row.cartridge_field], row
        if _target(target) != allow.V2_TARGET_FACILITY_PROFILE:
            # Hand-picked tables stay inside their subject; the facility profile is
            # open by model definition (operator decision 2026-11-13).
            assert row.cartridge_field in CARTRIDGE_SUBJECTS[spec.subject_type], row


def test_pinned_cartridge_declarations_match_plasticos_0_5_0():
    assert allow._thaw(allow.PLASTICOS_FACILITY_DECLARATIONS) == CARTRIDGE_DECLARATIONS


def test_starting_rows_are_exactly_the_reviewed_set():
    def rows(key):
        return {(r.cartridge_field, r.odoo_field, r.kind) for r in _spec(key).rows}

    assert rows(allow.V2_TARGET_PARTNER) == {
        ("name", "name", "char"),
        ("city", "city", "char"),
        ("zip_code", "zip", "char"),
        ("street", "street", "char"),
        ("street2", "street2", "char"),
        ("website", "website", "char"),
        ("email", "email", "char"),
        ("phone", "phone", "char"),
        ("state", "state_id", "many2one_code"),
    }
    assert "material_profile" not in allow.CONVERGE_V2_TARGETS
    with pytest.raises(KeyError):
        allow.resolve_v2_target("material_profile")
    assert rows(allow.V2_TARGET_FACILITY_PROFILE) == {
        ("contamination_tolerance", "contamination_tolerance_pct", "float"),
    }
    facility_subject = allow.resolve_v2_target(
        allow.V2_TARGET_FACILITY_PROFILE, FACILITY_FIELD_DEFS, subject=allow.V2_SUBJECT_FACILITY
    )
    assert facility_subject.subject_type == "facility"
    assert {(r.cartridge_field, r.odoo_field, r.kind) for r in facility_subject.rows} == {
        ("capacity_tons_month", "capacity_lbs_month", "integer"),
    }


def test_never_targets_and_unmapped_fields_have_no_row():
    for spec in allow.CONVERGE_V2_TARGETS.values():
        for row in spec.rows:
            assert row.odoo_field not in allow.CONVERGE_V2_NEVER_TARGETS
            assert row.cartridge_field not in allow.CONVERGE_V2_UNMAPPED
    assert set(allow.CONVERGE_V2_UNMAPPED) == {
        "tier",
        "capacity_tons_month",
        "material_grade",
        "material_forms",
        "certifications",
    }
    assert {"polymer_id", "form_id", "material_grade_id", "partner_id", "facility_profile_id"} <= (
        allow.CONVERGE_V2_NEVER_TARGETS
    )


def test_facility_profile_is_open_by_model_definition_minus_never_targets():
    eligible = set(allow.eligible_odoo_fields(FACILITY_FIELD_DEFS))
    assert eligible == {
        "avg_truckload_lbs",
        "iso_certified",
        "food_grade_certified",
        "min_lot_size_lbs",
        "freeform_notes",
        "contamination_tolerance_pct",
        "moisture_tolerance_pct",
        "capacity_lbs_month",
        "application_notes",
    }
    for never in ("id", "display_name", "create_uid", "partner_id", "crm_lead_id", "active", "message_partner_ids"):
        assert never not in eligible
    assert allow.field_ineligibility(FACILITY_FIELD_DEFS[3]) == "never a converge target"


def test_facility_profile_unmapped_cartridge_fields_are_listed_with_a_reason():
    _target, unmapped = allow.derive_facility_profile_target(FACILITY_FIELD_DEFS)
    assert set(unmapped) == {
        "facility_id",
        "name",
        "tier",
        "city",
        "state",
        "zip_code",
        "material_grade",
        "certifications",
        "street",
        "street2",
        "website",
        "email",
        "phone",
        "material_forms",
        "capacity_tons_month",
        "processed_polymers",
        "min_density",
        "max_density",
        "min_mfi",
        "max_mfi",
    }
    assert unmapped["min_density"] == allow.ADR134_RETIRED_REASON
    assert unmapped["processed_polymers"] == allow.ADR134_RETIRED_REASON
    assert unmapped["facility_id"] == "cartridge identity"
    assert unmapped["city"] == "subject 'facility': requested under that subject, not 'material'"
    assert unmapped["material_grade"] == "no facility-profile field of that name and no alias"
    _target, under_facility = allow.derive_facility_profile_target(FACILITY_FIELD_DEFS, subject="facility")
    assert under_facility["tier"] == "no facility-profile field of that name and no alias"


def test_an_unreviewed_cartridge_version_fails_closed():
    with pytest.raises(ValueError, match="no reviewed facility-profile vocabulary"):
        allow.resolve_v2_target(allow.V2_TARGET_FACILITY_PROFILE, FACILITY_FIELD_DEFS, version="0.7.0")


def _facility_subject_reply(reply):
    """Re-label a material-subject reply fixture as an answer to a facility-subject request."""
    for entry in reply["field_evidence"].values():
        entry["identity"]["subject_type"] = "facility"
    for proposal in reply["proposals"]:
        proposal["identity"]["subject_type"] = "facility"
    return reply


def _patch_vocabulary(monkeypatch, subject, **declarations):
    """Simulate adopting a cartridge revision: new names, their declarations and subject."""
    base = allow.PLASTICOS_CARTRIDGES["0.5.0"]
    vocabulary = allow.CartridgeVocabulary(
        allow._freeze({**allow._thaw(base.declarations), **declarations}),
        MappingProxyType({**base.subjects, **dict.fromkeys(declarations, subject)}),
    )
    monkeypatch.setattr(allow, "PLASTICOS_CARTRIDGES", MappingProxyType({"0.5.0": vocabulary}))


def test_facility_profile_target_needs_the_model_field_definitions():
    with pytest.raises(ValueError, match="field definitions"):
        allow.resolve_v2_target(allow.V2_TARGET_FACILITY_PROFILE)


def test_a_same_named_eligible_facility_field_maps_without_an_alias(monkeypatch):
    # The 0.6.0 candidate's shape: an Odoo-named, evidence-only field in the facility subject.
    _patch_vocabulary(monkeypatch, "facility", freeform_notes={"type": "string"})
    assert "freeform_notes" not in allow.FACILITY_PROFILE_V2_ALIASES
    row = allow.resolve_v2_target(allow.V2_TARGET_FACILITY_PROFILE, FACILITY_FIELD_DEFS, subject="facility").row(
        "freeform_notes"
    )
    assert (row.odoo_field, row.kind) == ("freeform_notes", "char")
    partner, run, profile = _facility_case()
    profile._values["freeform_notes"] = False
    profile._fields["freeform_notes"] = None
    request = build_converge_request_v2(
        _Env(),
        run,
        target="facility_profile",
        record=profile,
        cartridge=PIN,
        field_defs=FACILITY_FIELD_DEFS,
        subject="facility",
    )
    body = request.to_dict()
    assert body["subject"] == {"type": "facility", "role": "buyer"}
    assert [t["field"] for t in body["targets"]] == ["freeform_notes"]
    reply = _facility_subject_reply(_reply(allow.V2_TARGET_FACILITY_PROFILE))
    entry = copy.deepcopy(reply["field_evidence"]["contamination_tolerance"])
    entry.update(value="Accepts mixed bales", unit_status="not_applicable", declaration={"type": "string"})
    entry.pop("unit")
    reply["field_evidence"]["freeform_notes"] = entry
    reply["fields"]["freeform_notes"] = "Accepts mixed bales"
    reply["proposals"][0]["fields"].append("freeform_notes")
    reply["proposals"][0]["admitted_fields"].append("freeform_notes")
    for name in ("processed_polymers", "min_density", "contamination_tolerance"):
        reply["field_evidence"].pop(name)
        reply["fields"].pop(name, None)
        reply["proposals"][0]["fields"].remove(name)
        if name in reply["proposals"][0]["admitted_fields"]:
            reply["proposals"][0]["admitted_fields"].remove(name)
    response = parse_converge_response_v2(reply, request=request)
    assert response.usable, response.rejection
    plan = plan_converge_v2_writeback("facility_profile", response, request, FACILITY_FIELD_DEFS)
    decision = next(d for d in plan.decisions if d.cartridge_field == "freeform_notes")
    assert (decision.action, decision.odoo_field, decision.value) == (
        V2_PLAN_WRITE,
        "freeform_notes",
        "Accepts mixed bales",
    )


def test_a_never_target_is_refused_even_when_the_reply_proposes_it(monkeypatch):
    _patch_vocabulary(
        monkeypatch,
        "material",
        active={"type": "bool"},
        crm_lead_id={"type": "string"},
        partner_id={"type": "string"},
    )
    target, unmapped = allow.derive_facility_profile_target(FACILITY_FIELD_DEFS)
    for never in ("active", "crm_lead_id", "partner_id"):
        assert target.row(never) is None
        assert "never a converge target" in unmapped[never]
    request = _request(allow.V2_TARGET_FACILITY_PROFILE)
    assert not {"active", "crm_lead_id", "partner_id"} & {t["field"] for t in request.targets}
    reply = _reply(allow.V2_TARGET_FACILITY_PROFILE)
    proposed = copy.deepcopy(reply["field_evidence"]["processed_polymers"])
    proposed.update(value=False, declaration={"type": "bool"})
    reply["field_evidence"]["active"] = proposed
    reply["fields"]["active"] = False
    reply["proposals"][0]["fields"].append("active")
    reply["proposals"][0]["admitted_fields"].append("active")
    response = parse_converge_response_v2(reply, request=request)
    assert response.usable, response.rejection
    plan = plan_converge_v2_writeback("facility_profile", response, request, FACILITY_FIELD_DEFS)
    assert "active" not in {d.cartridge_field for d in plan.decisions}
    assert "active" not in {d.odoo_field for d in plan.writes}


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [(50000, "lb/month", 50000), (10, "t/month", 22046), (22.68, "t/month", 50001), (12.5, "lb/month", 13)],
)
def test_capacity_is_written_only_as_whole_pounds(value, unit, expected):
    partner, run, profile = _facility_case()
    profile._values["capacity_lbs_month"] = 0
    request = build_converge_request_v2(
        _Env(),
        run,
        target="facility_profile",
        record=profile,
        cartridge=PIN,
        field_defs=FACILITY_FIELD_DEFS,
        subject="facility",
    )
    assert [t["field"] for t in request.targets] == ["capacity_tons_month"]
    reply = _facility_subject_reply(_reply(allow.V2_TARGET_FACILITY_PROFILE))
    for name in ("processed_polymers", "min_density", "contamination_tolerance"):
        reply["field_evidence"].pop(name)
        reply["fields"].pop(name, None)
        reply["proposals"][0]["fields"].remove(name)
        if name in reply["proposals"][0]["admitted_fields"]:
            reply["proposals"][0]["admitted_fields"].remove(name)
    template = _reply(allow.V2_TARGET_FACILITY_PROFILE)["field_evidence"]["contamination_tolerance"]
    entry = copy.deepcopy(template)
    entry.update(value=value, unit=unit, identity={**entry["identity"], "subject_type": "facility"})
    reply["field_evidence"]["capacity_tons_month"] = entry
    reply["fields"]["capacity_tons_month"] = value
    reply["proposals"][0]["fields"].append("capacity_tons_month")
    reply["proposals"][0]["admitted_fields"].append("capacity_tons_month")
    response = parse_converge_response_v2(reply, request=request)
    plan = plan_converge_v2_writeback("facility_profile", response, request, FACILITY_FIELD_DEFS)
    assert plan.rejection is None
    decision = next(d for d in plan.decisions if d.cartridge_field == "capacity_tons_month")
    if expected is None:
        assert decision.skip_reason == V2_SKIP_UNIT
    else:
        assert (decision.action, decision.value) == (V2_PLAN_WRITE, expected)
        assert isinstance(decision.value, int)


def test_numeric_rows_name_their_odoo_unit_and_conversions():
    for spec in (_spec(t) for t in CASES):
        for row in spec.rows:
            if row.kind in allow.V2_NUMERIC_KINDS:
                assert 1.0 in row.units.values(), row
    contamination = _spec(allow.V2_TARGET_FACILITY_PROFILE).row("contamination_tolerance")
    assert dict(contamination.units) == {"percent": 1.0, "%": 1.0}


def test_table_is_immutable():
    row = allow.CONVERGE_V2_TARGETS[allow.V2_TARGET_PARTNER].rows[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.odoo_field = "comment"
    with pytest.raises(TypeError):
        allow.CONVERGE_V2_TARGETS["x"] = None
    with pytest.raises(TypeError):
        row.declaration["type"] = "int"


def test_table_refuses_a_numeric_row_without_units():
    with pytest.raises(ValueError, match="units"):
        allow.ConvergeV2FieldRow(
            "contamination_tolerance", "contamination_tolerance_pct", "float", allow._freeze({"type": "float"})
        )


# ── Request v2 shape (request.v2.md) ────────────────────────────────────────


@pytest.mark.parametrize("target", sorted(CASES))
def test_request_carries_only_v2_members_and_never_v1_field_selectors(target):
    body = _request(target).to_dict()
    assert set(body) <= REQUEST_V2_MEMBERS
    assert body["contract"] == CONVERGE_REQUEST_V2
    for forbidden in ("schema", "field_thresholds", "kb_context", "domain", "domain_id", "node_label"):
        assert forbidden not in body
    assert body["cartridge"] == {"id": "plasticos", "version": "0.5.0"}
    assert body["node"] == CARTRIDGE_NODE
    assert body["targets"], "targets must be non-empty"
    names = [t["field"] for t in body["targets"]]
    assert len(names) == len(set(names))
    spec = _spec(target)
    assert body["subject"]["type"] == spec.subject_type
    for t in body["targets"]:
        assert set(t) == {"field", "type"}
        assert t["type"] == CARTRIDGE_DECLARATIONS[t["field"]]
    for obs in body.get("observations", []):
        assert {"field", "value", "source_kind", "source_ref"} <= set(obs)
        assert set(obs) <= {"field", "value", "unit", "source_kind", "source_ref", "observed_at", "confidence"}
        assert obs["field"] in CARTRIDGE_DECLARATIONS
        assert "confidence" not in obs, "Odoo states no confidence it does not hold"
    json.dumps(body)  # JSON-serialisable as handed to the SDK


def test_partner_request_targets_only_empty_fields_and_observes_the_rest():
    body = _request(allow.V2_TARGET_PARTNER).to_dict()
    assert [t["field"] for t in body["targets"]] == ["city", "zip_code", "street2", "website", "state"]
    assert body["observations"] == [
        {"field": "name", "value": "Acme Recycling", "source_kind": "odoo_record", "source_ref": "res.partner:55#name"},
        {"field": "street", "value": "1 Main St", "source_kind": "odoo_record", "source_ref": "res.partner:55#street"},
        {
            "field": "email",
            "value": "ops@acme.example",
            "source_kind": "odoo_record",
            "source_ref": "res.partner:55#email",
        },
        {
            "field": "phone",
            "value": "+1 704 555 0100",
            "source_kind": "odoo_record",
            "source_ref": "res.partner:55#phone",
        },
    ]
    assert body["subject"] == {"type": "facility", "role": "supplier"}
    assert body["entity"]["id"] == "res.partner:55"
    assert body["entity"]["_odoo_entity_id"] == "res.partner:55"
    assert body["object_type"] == "res.partner"
    assert body["idempotency_key"] == "odoo:enrichment:plasticos:plasticos.enrichment.run:7"


def test_supplier_facility_profile_request_asks_capability_fields_under_material():
    body = _request(SUPPLIER_FACILITY).to_dict()
    assert body["subject"] == {"type": "material", "role": "supplier"}
    assert [t["field"] for t in body["targets"]] == ["contamination_tolerance"]
    assert "observations" not in body, "capacity is a facility-subject field and is not sent under material"
    assert body["entity"]["id"] == "res.partner:56"
    assert body["odoo"]["target_model"] == "plasticos.facility.profile"
    assert body["odoo"]["target_res_id"] == 402


def test_a_material_profile_cannot_start_a_v2_run():
    partner = _partner(70, name="Material Owner")
    material = _Rec("plasticos.material.profile", 301, partner_id=partner, density_min=0.0)
    with pytest.raises(KeyError):
        build_converge_request_v2(_Env(), _run(14, partner), target="material_profile", record=material, cartridge=PIN)
    with pytest.raises(ValueError, match="enriches plasticos.facility.profile"):
        build_converge_request_v2(
            _Env(),
            _run(14, partner),
            target="facility_profile",
            record=material,
            cartridge=PIN,
            field_defs=FACILITY_FIELD_DEFS,
        )


def test_facility_profile_request_observes_filled_tolerances_with_their_odoo_unit():
    body = _request(allow.V2_TARGET_FACILITY_PROFILE).to_dict()
    assert body["subject"] == {"type": "material", "role": "buyer"}
    assert [t["field"] for t in body["targets"]] == ["contamination_tolerance"]
    assert body["targets"][0]["type"] == CARTRIDGE_DECLARATIONS["contamination_tolerance"]
    assert "observations" not in body


def test_retired_polymer_and_density_fields_are_not_requested():
    body = _request(allow.V2_TARGET_FACILITY_PROFILE).to_dict()
    assert "processed_polymers" not in {t["field"] for t in body["targets"]}
    assert "min_density" not in {t["field"] for t in body["targets"]}


def test_sha256_pin_travels_when_set():
    body = _request(allow.V2_TARGET_PARTNER, CartridgePin("plasticos", "0.5.0", "deadbeef")).to_dict()
    assert body["cartridge"] == {"id": "plasticos", "version": "0.5.0", "sha256": "deadbeef"}


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        (("supplier",), "supplier"),
        (("buyer",), "buyer"),
        (("buyer", "supplier"), None),
        ((), None),
        (("carrier",), None),
    ],
)
def test_role_is_sent_only_when_the_partners_own_tags_are_unambiguous(roles, expected):
    assert derive_subject_role(_partner(1, roles=roles)) == expected
    partner = _partner(60, roles=roles)
    body = build_converge_request_v2(
        _Env(), _run(10, partner), target="partner", record=partner, cartridge=PIN
    ).to_dict()
    assert body["subject"].get("role") == expected
    if expected is None:
        assert "role" not in body["subject"]


def test_nothing_to_request_when_every_mapped_field_is_filled():
    partner = _partner(
        61,
        name="N",
        city="C",
        zip="Z",
        street="S",
        street2="S2",
        website="W",
        email="E",
        phone="P",
        state_id=_Coded("NC"),
    )
    with pytest.raises(ConvergeV2NothingToRequest):
        build_converge_request_v2(_Env(), _run(11, partner), target="partner", record=partner, cartridge=PIN)


def test_builder_refuses_a_record_of_the_wrong_model():
    partner = _partner(71, name="Material Owner")
    run = _run(15, partner)
    profile = _Rec("plasticos.material.profile", 302, partner_id=partner)
    with pytest.raises(ValueError, match="enriches plasticos.facility.profile"):
        build_converge_request_v2(
            _Env(), run, target="facility_profile", record=profile, cartridge=PIN, field_defs=FACILITY_FIELD_DEFS
        )


def test_builder_refuses_a_profile_of_another_partner():
    _partner_rec, _run_rec, profile = _supplier_facility_case()
    stranger = _partner(99, name="Stranger")
    with pytest.raises(ValueError, match="does not belong to the run partner"):
        build_converge_request_v2(
            _Env(),
            _run(12, stranger),
            target="facility_profile",
            record=profile,
            cartridge=PIN,
            field_defs=FACILITY_FIELD_DEFS,
        )


def test_builder_refuses_another_partner_as_the_partner_target():
    partner, _run_rec, _record = _partner_case()
    stranger = _partner(98, name="Stranger")
    with pytest.raises(ValueError, match="does not belong to the run partner"):
        build_converge_request_v2(_Env(), _run(13, stranger), target="partner", record=partner, cartridge=PIN)


def test_builder_refuses_a_lead_owned_facility_profile():
    partner, run, profile = _facility_case()
    profile._values["partner_id"] = False
    with pytest.raises(ValueError, match="lead-owned"):
        build_converge_request_v2(
            _Env(), run, target="facility_profile", record=profile, cartridge=PIN, field_defs=FACILITY_FIELD_DEFS
        )


def test_request_is_immutable():
    request = _request(allow.V2_TARGET_PARTNER)
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.node = "Other"
    with pytest.raises(TypeError):
        request.targets[0]["field"] = "tier"
    body = request.to_dict()
    body["targets"][0]["field"] = "tier"
    assert request.to_dict()["targets"][0]["field"] == "city"


# ── Response v2 parsing (response.v2.md) ────────────────────────────────────


def test_partner_reply_parses_every_evidence_state():
    _req, resp = _parse(allow.V2_TARGET_PARTNER)
    assert resp.usable, resp.rejection
    assert resp.contract_version == CONVERGE_RESPONSE_V2
    assert resp.resolution.cartridge_version == "0.5.0"
    states = {name: e.state for name, e in resp.field_evidence.items()}
    assert states == {
        "name": "observed",
        "city": "external_claim",
        "zip_code": "inferred",
        "street2": "unknown",
        "website": "conflicting",
        "state": "external_claim",
    }
    zip_code = resp.field_evidence["zip_code"]
    assert zip_code.derivation.inputs == ("city",)
    assert resp.field_evidence["street2"].has_value is False
    assert resp.field_evidence["street2"].unknown_reason == "no_evidence"
    assert len(resp.field_evidence["website"].conflict) == 2
    assert resp.field_evidence["city"].sources[0].citations == ("https://example.invalid/acme",)
    assert resp.proposals[0].admitted_fields == ("city", "zip_code")


def test_parsed_reply_is_immutable():
    _req, resp = _parse(allow.V2_TARGET_FACILITY_PROFILE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        resp.rejection = None
    with pytest.raises(TypeError):
        resp.field_evidence["x"] = None
    value = resp.field_evidence["processed_polymers"].value
    assert isinstance(value, tuple)
    with pytest.raises(TypeError):
        value[0]["code"] = "PVC"


def test_v1_shaped_reply_to_a_v2_request_is_rejected_not_read_from_fields():
    reply = _reply(allow.V2_TARGET_PARTNER)
    for key in ("contract_version", "field_evidence", "proposals", "resolution"):
        reply.pop(key)
    request, resp = _parse(allow.V2_TARGET_PARTNER, reply)
    assert not resp.usable
    assert resp.rejection.startswith(V2_REJECT_V1_REPLY)
    assert resp.field_evidence == {}
    plan = plan_converge_v2_writeback(allow.V2_TARGET_PARTNER, resp, request)
    assert plan.writes == ()
    assert plan.rejection == resp.rejection


@pytest.mark.parametrize("version", ["eie.converge.response/v3", "eie.converge.response/v1", "", 2])
def test_unrecognised_contract_version_is_rejected(version):
    reply = _reply(allow.V2_TARGET_PARTNER)
    reply["contract_version"] = version
    _req, resp = _parse(allow.V2_TARGET_PARTNER, reply)
    assert resp.rejection.startswith(V2_REJECT_UNSUPPORTED_CONTRACT)


def test_unrecognised_evidence_state_is_rejected():
    reply = _reply(allow.V2_TARGET_PARTNER)
    reply["field_evidence"]["city"]["state"] = "reported"
    _req, resp = _parse(allow.V2_TARGET_PARTNER, reply)
    assert resp.rejection.startswith(V2_REJECT_MALFORMED)
    assert "reported" in resp.rejection
    assert resp.field_evidence == {}


def test_requested_field_without_an_entry_is_rejected():
    reply = _reply(allow.V2_TARGET_PARTNER)
    del reply["field_evidence"]["street2"]
    reply["proposals"][0]["fields"].remove("street2")
    _req, resp = _parse(allow.V2_TARGET_PARTNER, reply)
    assert resp.rejection.startswith(V2_REJECT_MISSING_ENTRY)
    assert "street2" in resp.rejection


def _mutate(target, mutation):
    reply = _reply(target)
    mutation(reply)
    return _parse(target, reply)[1]


MALFORMED = {
    "value on unknown": lambda r: r["field_evidence"]["street2"].__setitem__("value", "x"),
    "no value on claim": lambda r: r["field_evidence"]["state"].pop("value"),
    "observed admitted": lambda r: r["field_evidence"]["name"].__setitem__("admitted", True),
    "unknown admitted": lambda r: r["field_evidence"]["street2"].__setitem__("admitted", True),
    "admitted not bool": lambda r: r["field_evidence"]["city"].__setitem__("admitted", "yes"),
    "confidence above 1": lambda r: r["field_evidence"]["city"].__setitem__("confidence", 1.2),
    "confidence bool": lambda r: r["field_evidence"]["city"].__setitem__("confidence", True),
    "confidence on unknown": lambda r: r["field_evidence"]["street2"].__setitem__("confidence", 0.4),
    "declaration missing": lambda r: r["field_evidence"]["city"].pop("declaration"),
    "unit without stated": lambda r: r["field_evidence"]["city"].__setitem__("unit", "m"),
    "stated without unit": lambda r: r["field_evidence"]["city"].__setitem__("unit_status", "stated"),
    "unit_status unknown word": lambda r: r["field_evidence"]["city"].__setitem__("unit_status", "metric"),
    "claim without sources": lambda r: r["field_evidence"]["city"].__setitem__("sources", []),
    "source type unknown": lambda r: r["field_evidence"]["city"]["sources"][0].__setitem__("source_type", "web"),
    "inferred without derivation": lambda r: r["field_evidence"]["zip_code"].__setitem__("derivation", None),
    "derivation without version": lambda r: r["field_evidence"]["zip_code"]["derivation"].pop("rule_or_model_version"),
    "derivation input without entry": lambda r: r["field_evidence"]["zip_code"]["derivation"].__setitem__(
        "inputs", ["county"]
    ),
    "conflict resolved": lambda r: r["field_evidence"]["website"]["conflict"].__setitem__("resolution", "a"),
    "one conflict candidate": lambda r: r["field_evidence"]["website"]["conflict"]["candidates"].pop(),
    "unknown without reason": lambda r: r["field_evidence"]["street2"].__setitem__("unknown_reason", None),
    "unknown reason word": lambda r: r["field_evidence"]["street2"].__setitem__("unknown_reason", "nope"),
    "identity of another subject": lambda r: r["field_evidence"]["city"]["identity"].__setitem__(
        "subject_ref", "res.partner:99"
    ),
    "identity role changed": lambda r: r["field_evidence"]["city"]["identity"].__setitem__("role", "buyer"),
    "fields lists an unadmitted entry": lambda r: r["fields"].__setitem__("state", "NC"),
    "fields misses an admitted entry": lambda r: r["fields"].pop("city"),
    "fields value differs": lambda r: r["fields"].__setitem__("city", "Raleigh"),
    "proposals missing": lambda r: r.pop("proposals"),
    "proposal admitted disagrees": lambda r: r["proposals"][0]["admitted_fields"].pop(),
    "proposal review not required": lambda r: r["proposals"][0]["review"].__setitem__("required", False),
    "entry is not an object": lambda r: r["field_evidence"].__setitem__("city", "Charlotte"),
    "run state unrecognised": lambda r: r.__setitem__("state", "done"),
    "resolution missing": lambda r: r.pop("resolution"),
}


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_a_malformed_reply_rejects_all_of_its_evidence(case):
    resp = _mutate(allow.V2_TARGET_PARTNER, MALFORMED[case])
    assert not resp.usable, case
    assert resp.rejection.startswith(V2_REJECT_MALFORMED), resp.rejection
    assert resp.field_evidence == {} and resp.proposals == ()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r["resolution"].__setitem__("cartridge_version", "0.6.0"),
        lambda r: r["resolution"].__setitem__("cartridge_id", "other"),
        lambda r: r["resolution"].__setitem__("node", "Carrier"),
    ],
)
def test_a_reply_resolved_against_another_cartridge_revision_is_rejected(mutation):
    resp = _mutate(allow.V2_TARGET_PARTNER, mutation)
    assert resp.rejection.startswith(V2_REJECT_RESOLUTION)


def test_sha256_pin_is_checked_against_the_resolution():
    request = _request(allow.V2_TARGET_PARTNER, CartridgePin("plasticos", "0.5.0", "ffff"))
    resp = parse_converge_response_v2(_reply(allow.V2_TARGET_PARTNER), request=request)
    assert resp.rejection.startswith(V2_REJECT_RESOLUTION)


@pytest.mark.parametrize(
    ("state", "reason"),
    [("degraded", "deadline_exceeded"), ("failed", "no_valid_responses"), ("completed", "late_failure")],
)
def test_only_a_completed_run_without_failure_reason_is_usable(state, reason):
    reply = _reply(allow.V2_TARGET_PARTNER)
    reply["state"] = state
    reply["failure_reason"] = reason
    _req, resp = _parse(allow.V2_TARGET_PARTNER, reply)
    assert resp.rejection.startswith(V2_REJECT_NOT_COMPLETED)
    assert reason in resp.rejection


def test_a_refusal_without_evidence_is_rejected_with_its_code():
    refusal = {
        "contract_version": CONVERGE_RESPONSE_V2,
        "state": "failed",
        "failure_reason": "cartridge_pin_mismatch: version 0.5.0 requested, 0.6.0 loaded",
        "fields": {},
        "proposals": [],
    }
    _req, resp = _parse(allow.V2_TARGET_PARTNER, refusal)
    assert "cartridge_pin_mismatch" in resp.rejection


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.__setitem__("state", ["completed"]),
        lambda r: r["field_evidence"]["city"].__setitem__("state", {"v": 1}),
        lambda r: r["field_evidence"]["city"].__setitem__("unit_status", ["stated"]),
        lambda r: r["field_evidence"]["city"]["sources"][0].__setitem__("source_type", ["provider"]),
        lambda r: r["field_evidence"]["street2"].__setitem__("unknown_reason", ["no_evidence"]),
        lambda r: r["proposals"][0]["review"].__setitem__("reasons", [["contains_unknown"]]),
        lambda r: r["proposals"][0].__setitem__("fields", [["city"]]),
    ],
)
def test_a_non_string_where_a_string_is_due_rejects_instead_of_raising(mutation):
    resp = _mutate(allow.V2_TARGET_PARTNER, mutation)
    assert not resp.usable
    assert resp.rejection.startswith(V2_REJECT_MALFORMED), resp.rejection


def test_non_object_payload_is_rejected():
    _req, resp = _parse(allow.V2_TARGET_PARTNER, ["not", "an", "object"])
    assert resp.rejection.startswith(V2_REJECT_MALFORMED)


# ── Writeback plan (approved evidence-state policy) ─────────────────────────


def _plan(target, reply=None):
    request, resp = _parse(target, reply)
    return plan_converge_v2_writeback(_target(target), resp, request, _defs(target))


def _by_field(plan):
    return {d.cartridge_field: d for d in plan.decisions}


def test_partner_plan_writes_only_admitted_claims_and_inferences():
    plan = _plan(allow.V2_TARGET_PARTNER)
    assert plan.rejection is None
    decisions = _by_field(plan)
    assert set(decisions) == {"city", "zip_code", "street2", "website", "state"}
    assert (decisions["city"].action, decisions["city"].value) == (V2_PLAN_WRITE, "Charlotte")
    assert (decisions["zip_code"].action, decisions["zip_code"].value) == (V2_PLAN_WRITE, "28202")
    assert decisions["zip_code"].odoo_field == "zip"
    assert decisions["street2"].skip_reason == V2_SKIP_UNKNOWN
    assert decisions["website"].skip_reason == V2_SKIP_CONFLICTING
    assert decisions["state"].skip_reason == V2_SKIP_NOT_ADMITTED
    assert all(d.value is None for d in plan.decisions if d.action == V2_PLAN_SKIP)
    assert "name" not in decisions, "an observation the request did not target is never planned"


def test_supplier_facility_plan_skips_the_kept_tolerance_when_the_reply_has_no_evidence():
    decisions = _by_field(_plan(SUPPLIER_FACILITY))
    assert set(decisions) == {"contamination_tolerance"}
    assert decisions["contamination_tolerance"].action == V2_PLAN_SKIP
    assert decisions["contamination_tolerance"].skip_reason == V2_SKIP_UNKNOWN
    assert decisions["contamination_tolerance"].odoo_field == "contamination_tolerance_pct"


def test_facility_plan_writes_contamination():
    decisions = _by_field(_plan(allow.V2_TARGET_FACILITY_PROFILE))
    assert set(decisions) == {"contamination_tolerance"}
    contamination = decisions["contamination_tolerance"]
    assert contamination.action == V2_PLAN_WRITE
    assert contamination.value == pytest.approx(5.0)
    assert contamination.odoo_field == "contamination_tolerance_pct"


def test_a_declaration_that_drifted_from_the_reviewed_row_rejects_the_plan():
    reply = _reply(SUPPLIER_FACILITY)
    reply["field_evidence"]["contamination_tolerance"]["declaration"] = {"type": "string"}
    plan = _plan(SUPPLIER_FACILITY, reply)
    assert plan.rejection and "declaration" in plan.rejection
    assert plan.decisions == ()


def test_declared_unit_on_a_declaration_is_not_drift():
    reply = _reply(SUPPLIER_FACILITY)
    reply["field_evidence"]["contamination_tolerance"]["declaration"] = {"type": "float", "unit": "percent"}
    assert _plan(SUPPLIER_FACILITY, reply).rejection is None


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        (SUPPLIER_FACILITY, "contamination_tolerance", "0.94"),
        (SUPPLIER_FACILITY, "contamination_tolerance", True),
        (allow.V2_TARGET_PARTNER, "city", 12),
        (allow.V2_TARGET_PARTNER, "city", "  "),
    ],
)
def test_a_value_of_the_wrong_shape_rejects_the_plan(target, field, value):
    reply = _reply(target)
    reply["field_evidence"][field]["value"] = value
    reply["fields"][field] = value
    plan = _plan(target, reply)
    assert plan.rejection, (field, value)
    assert plan.writes == ()


def test_plan_of_a_rejected_reply_is_empty():
    reply = _reply(allow.V2_TARGET_FACILITY_PROFILE)
    reply["state"] = "degraded"
    plan = _plan(allow.V2_TARGET_FACILITY_PROFILE, reply)
    assert plan.decisions == () and plan.rejection.startswith(V2_REJECT_NOT_COMPLETED)


# ── Configuration ───────────────────────────────────────────────────────────


def test_v1_is_the_default_contract():
    assert resolve_converge_contract(_Env()).contract == CONVERGE_CONTRACT_V1
    selection = resolve_converge_contract(_Env({"plasticos.gate.converge_contract": "v1"}))
    assert not selection.is_v2


def test_v2_requires_the_cartridge_pin():
    with pytest.raises(GateIntegrationError, match="converge_cartridge_version"):
        resolve_converge_contract(
            _Env({"plasticos.gate.converge_contract": "v2", "plasticos.gate.converge_cartridge_id": "plasticos"})
        )


def test_v2_selection_carries_the_pin():
    selection = resolve_converge_contract(
        _Env(
            {
                "plasticos.gate.converge_contract": "V2",
                "plasticos.gate.converge_cartridge_id": "plasticos",
                "plasticos.gate.converge_cartridge_version": "0.5.0",
            }
        )
    )
    assert selection.contract == CONVERGE_CONTRACT_V2
    assert (selection.cartridge_id, selection.cartridge_version, selection.cartridge_sha256) == (
        "plasticos",
        "0.5.0",
        None,
    )


def test_an_unknown_contract_value_fails_closed():
    with pytest.raises(GateIntegrationError, match="must be"):
        resolve_converge_contract(_Env({"plasticos.gate.converge_contract": "v3"}))


def test_seed_keeps_v1_selected():
    seed = (ROOT / "plasticos_gate" / "data" / "gate_icp_seed.xml").read_text()
    assert '<field name="key">plasticos.gate.converge_contract</field>\n        <field name="value">v1</field>' in seed


# ── v1 is unchanged ─────────────────────────────────────────────────────────

V1_GOLDEN = {
    "entity": {"id": "res.partner:55", "_odoo_entity_id": "res.partner:55"},
    "object_type": "plasticos",
    "objective": "Full entity enrichment and inference",
    "max_variations": 5,
    "consensus_threshold": 0.8,
    "kb_context": "plasticos",
    "schema": {
        "city": "string",
        "email": "string",
        "name": "string",
        "phone": "string",
        "street": "string",
        "street2": "string",
        "website": "string",
        "zip": "string",
    },
    "idempotency_key": "odoo:enrichment:plasticos:plasticos.enrichment.run:7",
    "odoo": {
        "model": "plasticos.enrichment.run",
        "record_id": 7,
        "company_id": 1,
        "user_id": 2,
        "db_name": "plasticos",
        "correlation_id": "plasticos.enrichment.run:7",
    },
}


class _V1Partner:
    _fields: dict = {}

    def __init__(self, pid):
        self.id = pid


class _V1Run:
    _name = "plasticos.enrichment.run"
    source_ids = ()
    gate_attempt = 1

    def __init__(self):
        self.id = 7
        self.partner_id = _V1Partner(55)


def test_v1_request_is_byte_for_byte_unchanged():
    payload = build_converge_request(_Env(), _V1Run()).to_dict()
    assert json.dumps(payload, sort_keys=True) == json.dumps(V1_GOLDEN, sort_keys=True)
    assert list(payload) == list(V1_GOLDEN), "key order is part of the bytes on the wire"


def test_v1_allowlist_and_mapper_are_unchanged():
    assert allow.PARTNER_WRITEBACK_FIELD_ALLOWLIST == {
        "name",
        "website",
        "city",
        "zip",
        "street",
        "street2",
        "email",
        "phone",
    }
    reply = _reply(allow.V2_TARGET_PARTNER)
    reply["fields"] = {"city": "Charlotte", "comment": "x"}
    mapped = map_converge_response(copy.deepcopy(reply))
    assert mapped.status == "ok"
    assert partner_writeback_from_converge(mapped) == {"city": "Charlotte"}


def test_a_number_with_unit_status_unknown_is_skipped_as_on_cartridge_0_5_0():
    """Cartridge 0.5.0 declares no unit, so a kept number arrives with unit_status 'unknown' (decision 4)."""
    reply = _reply(allow.V2_TARGET_FACILITY_PROFILE)
    entry = reply["field_evidence"]["contamination_tolerance"]
    entry["unit_status"] = "unknown"
    entry.pop("unit", None)
    decisions = _by_field(_plan(allow.V2_TARGET_FACILITY_PROFILE, reply))
    assert decisions["contamination_tolerance"].action == V2_PLAN_SKIP
    assert decisions["contamination_tolerance"].skip_reason == V2_SKIP_UNIT
    assert "no governing unit" in decisions["contamination_tolerance"].detail


def test_engine_and_spec_declaration_forms_compare_equal():
    from plasticos_gate.services.gate_mappers import _declaration_shape

    spec_form = CARTRIDGE_DECLARATIONS["processed_polymers"]  # declaration compare only; the field is not written
    engine_form = {
        "type": "list",
        "required": False,
        "items": {"type": "map", "required": False, "properties": {"code": {"type": "string", "required": True}}},
    }
    assert _declaration_shape(spec_form) == _declaration_shape(engine_form)


# ── Governing unit (decision 4 as amended 2026-11-13) ───────────────────────


def _unknown_unit_reply_with_declared_units(unit_by_field):
    reply = _reply(allow.V2_TARGET_FACILITY_PROFILE)
    for name, unit in unit_by_field.items():
        entry = reply["field_evidence"][name]
        entry["unit_status"] = "unknown"
        entry.pop("unit", None)
        entry["declaration"] = {**entry["declaration"], "unit": unit}
    return reply


def test_the_declared_unit_governs_when_the_value_states_none():
    reply = _unknown_unit_reply_with_declared_units({"contamination_tolerance": "percent"})
    decisions = _by_field(_plan(allow.V2_TARGET_FACILITY_PROFILE, reply))
    assert decisions["contamination_tolerance"].action == V2_PLAN_WRITE
    assert decisions["contamination_tolerance"].value == pytest.approx(5.0)
    assert decisions["contamination_tolerance"].source_unit == "percent"


def test_a_stated_value_unit_overrides_the_declared_unit():
    reply = _reply(allow.V2_TARGET_FACILITY_PROFILE)
    entry = reply["field_evidence"]["contamination_tolerance"]
    entry["unit"] = "kg/m3"
    entry["unit_status"] = "stated"
    entry["declaration"] = {**entry["declaration"], "unit": "percent"}
    decisions = _by_field(_plan(allow.V2_TARGET_FACILITY_PROFILE, reply))
    assert decisions["contamination_tolerance"].skip_reason == V2_SKIP_UNIT


def test_a_declared_unit_the_row_does_not_accept_is_skipped():
    reply = _unknown_unit_reply_with_declared_units({"contamination_tolerance": "kg/m3"})
    decisions = _by_field(_plan(allow.V2_TARGET_FACILITY_PROFILE, reply))
    assert decisions["contamination_tolerance"].skip_reason == V2_SKIP_UNIT


def test_capacity_keeps_the_original_value_and_unit_for_provenance():
    partner, run, profile = _facility_case()
    profile._values["capacity_lbs_month"] = 0
    request = build_converge_request_v2(
        _Env(),
        run,
        target="facility_profile",
        record=profile,
        cartridge=PIN,
        field_defs=FACILITY_FIELD_DEFS,
        subject="facility",
    )
    reply = _facility_subject_reply(_reply(allow.V2_TARGET_FACILITY_PROFILE))
    template = copy.deepcopy(reply["field_evidence"]["contamination_tolerance"])
    for name in ("processed_polymers", "min_density", "contamination_tolerance"):
        reply["field_evidence"].pop(name)
        reply["fields"].pop(name, None)
        reply["proposals"][0]["fields"].remove(name)
        if name in reply["proposals"][0]["admitted_fields"]:
            reply["proposals"][0]["admitted_fields"].remove(name)
    template.update(value=22.68, unit_status="unknown", declaration={"type": "float", "unit": "t/month"})
    template.pop("unit")
    reply["field_evidence"]["capacity_tons_month"] = template
    reply["fields"]["capacity_tons_month"] = 22.68
    reply["proposals"][0]["fields"].append("capacity_tons_month")
    reply["proposals"][0]["admitted_fields"].append("capacity_tons_month")
    response = parse_converge_response_v2(reply, request=request)
    plan = plan_converge_v2_writeback("facility_profile", response, request, FACILITY_FIELD_DEFS)
    decision = plan.decisions[0]
    assert (decision.value, decision.source_value, decision.source_unit) == (50001, 22.68, "t/month")


# ── Cartridge 0.6.0 candidate (EIE PR #348 at bd345a0) ──────────────────────


def test_0_6_0_candidate_is_listed_but_0_5_0_stays_the_default():
    assert allow.PLASTICOS_CARTRIDGES["0.5.0"].status == "reviewed"
    assert allow.PLASTICOS_CARTRIDGES["0.6.0"].status == "candidate@bd345a0"
    new = set(allow.PLASTICOS_CARTRIDGES["0.6.0"].declarations) - set(allow.PLASTICOS_CARTRIDGES["0.5.0"].declarations)
    assert len(new) == 27
    assert "food_grade_certified" not in allow.PLASTICOS_CARTRIDGES["0.6.0"].declarations, "stays CEG-owned"
    assert (
        resolve_converge_contract(
            _Env(
                {
                    "plasticos.gate.converge_contract": "v2",
                    "plasticos.gate.converge_cartridge_id": "plasticos",
                    "plasticos.gate.converge_cartridge_version": "0.5.0",
                }
            )
        ).cartridge_version
        == "0.5.0"
    )


def test_adopting_0_6_0_needs_only_the_pin():
    facility = allow.resolve_v2_target(
        allow.V2_TARGET_FACILITY_PROFILE, FACILITY_FIELD_DEFS, subject="facility", version="0.6.0"
    )
    rows = {r.cartridge_field: r for r in facility.rows}
    assert rows["capacity_tons_month"].odoo_field == "capacity_lbs_month"
    for same_named in ("freeform_notes", "application_notes", "iso_certified"):
        assert rows[same_named].odoo_field == same_named
        assert same_named not in allow.FACILITY_PROFILE_V2_ALIASES
    for retired in ("handles_bales", "process_type", "equipment_type_ids", "form_preference_id"):
        assert retired not in rows
    _spec, unmapped = allow.derive_facility_profile_target(FACILITY_FIELD_DEFS, subject="facility", version="0.6.0")
    assert unmapped["equipment_type_ids"] == allow.ADR134_RETIRED_REASON
    assert dict(rows["avg_truckload_lbs"].units) == {"lb": 1.0, "lbs": 1.0}
    assert dict(rows["moisture_tolerance_pct"].units) == {"percent": 1.0, "%": 1.0}
    material = allow.resolve_v2_target(
        allow.V2_TARGET_FACILITY_PROFILE, FACILITY_FIELD_DEFS, subject="material", version="0.6.0"
    )
    assert {r.cartridge_field for r in material.rows} == {"contamination_tolerance"}


def test_a_0_6_0_request_never_sends_a_unit_in_a_target_type():
    partner, run, profile = _facility_case()
    request = build_converge_request_v2(
        _Env(),
        run,
        target="facility_profile",
        record=profile,
        cartridge=CartridgePin("plasticos", "0.6.0"),
        field_defs=FACILITY_FIELD_DEFS,
    )
    targets = {t["field"]: t["type"] for t in request.to_dict()["targets"]}
    assert "min_density" not in targets
    assert targets["contamination_tolerance"] == {"type": "float"}
    assert all("unit" not in json.dumps(t) for t in targets.values())

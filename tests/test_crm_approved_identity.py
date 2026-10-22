"""Approved VanillaSoft identity helpers. No Odoo runtime."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest

from plasticos_crm_sync.adapters.vanillasoft.adapter import contact_to_canonical
from plasticos_crm_sync.services.approved_identity import (
    ACTIVE_COMPANY_CP_BY_VS,
    PINNED_ERP_COUNT,
    PINNED_SHA256,
    PINNED_VS_COUNT,
    CrosswalkError,
    comment_blocks,
    comment_with_note,
    contact_note_text,
    phone_kinds,
    phone_match_key,
    validate_crosswalk,
    without_duplicate_contacts,
)
from tests.test_crm_sync_classification import _harness, _lead, _Model, _outcomes

ROOT = Path(__file__).resolve().parents[1]
PACK_CSV = (
    ROOT
    / "docs"
    / "campaigns"
    / "PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21"
    / "PRIVATE_INPUTS"
    / "03_APPROVED_CONTACT_CROSSWALK.csv"
)


def _csv(rows: list[tuple[str, str]]) -> str:
    lines = ["erp_ct_id,vanillasoft_contact_id", *[f"{ct},{vs}" for ct, vs in rows], ""]
    return "\n".join(lines)


def test_pinned_crosswalk_constants():
    """Pins the constants only. It does not prove the operator file."""
    assert PINNED_SHA256 == "9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1"
    assert PINNED_VS_COUNT == 759
    assert PINNED_ERP_COUNT == 691


def test_operator_crosswalk_file_matches_the_pinned_census():
    # Legitimate exception (95-test-fix-policy): the operator file carries contact
    # identities, is gitignored, and is never in CI. Without it the approved-file
    # claim is UNVERIFIED and is reported as a skip, never as a pass.
    # Removal trigger: a trusted, PII-free census input committed beside the receipt.
    if not PACK_CSV.is_file():
        pytest.skip(f"UNVERIFIED: operator crosswalk absent at {PACK_CSV.relative_to(ROOT)}")
    raw = PACK_CSV.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PINNED_SHA256
    mapping = validate_crosswalk(raw.decode("utf-8"))
    assert len(mapping) == PINNED_VS_COUNT
    assert len({ct_id for ct_id in mapping.values() if ct_id}) == PINNED_ERP_COUNT
    assert mapping["572648103"] == "2350001"
    assert mapping["1082805107"] == "192650001"
    assert mapping["573474327"] == "39150001"
    assert mapping["572648242"] == "8750001"
    assert mapping["619579299"] == "148650001"
    assert mapping["625031140"] == "9500001"
    assert mapping["1085161977"] == ""
    assert mapping["572647290"] == ""
    assert mapping["700174793"] == ""
    assert mapping["683417624"] == ""
    assert mapping["609608749"] == ""
    assert mapping["715993397"] == ""
    assert ACTIVE_COMPANY_CP_BY_VS["683417624"] == "1380"
    assert ACTIVE_COMPANY_CP_BY_VS["609608749"] == "2461"
    assert ACTIVE_COMPANY_CP_BY_VS["715993397"] == "2076"
    assert "572648239" not in mapping
    assert "1045036935" not in mapping
    assert "1179868294" not in mapping


def test_crosswalk_rejects_a_second_erp_target_for_one_contact():
    body = _csv([("10", "20"), ("11", "20")])
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    with pytest.raises(CrosswalkError, match="more than one ERP"):
        validate_crosswalk(body, expected_sha256=digest, expected_vs=1, expected_erp=1)


def test_contact_note_is_the_notes_custom_field_not_a_call_comment():
    raw = {
        "contact_id": "1",
        "custom_fields": [
            {"name": "Notes", "value": "CRM history"},
            {"name": "Notes (LDPE)", "value": "film"},
        ],
        "comment": "call comment",
    }
    dto = contact_to_canonical(raw)
    assert dto.contact_note == "CRM history"
    assert contact_note_text({"Notes (LDPE)": "film"}) == ""


def test_crm_note_is_appended_after_the_erp_notes_and_replays():
    erp = "<p>negotiate prices with Rich\nrequest PO</p>"
    first = comment_with_note(erp, "CRM history & terms")
    assert first == erp + "<p>CRM history &amp; terms</p>"
    assert comment_blocks(first) == ("negotiate prices with Rich request PO", "CRM history & terms")
    assert comment_with_note(first, "CRM history & terms") is None
    second = comment_with_note(first, "second contact note")
    assert comment_blocks(second)[-1] == "second contact note"
    assert comment_with_note(second, "CRM history & terms") is None
    assert comment_with_note(False, "only CRM") == "<p>only CRM</p>"
    assert comment_with_note(erp, "  ") is None


def test_note_presence_is_a_whole_paragraph_not_a_substring():
    assert comment_with_note("<p>look here</p>", "ok") == "<p>look here</p><p>ok</p>"
    assert comment_with_note("<p>first line</p><p>second line</p>", "first line\nsecond line") is None


def test_phone_token_match_is_the_whole_number():
    kinds = phone_kinds(
        [
            {"name": "direct", "number": "555-0100"},
            {"name": "mobile 1", "number": "(555) 201-0101"},
            {"name": "mobile 2", "number": "+1 (555) 201-0101"},
            {"name": "mobile 3", "number": "5552010101", "disabled": True},
            {"name": "office", "number": "555-0100"},
        ]
    )
    assert kinds == (("other", "555-0100"), ("mobile", "(555) 201-0101"))
    assert phone_match_key("+1 (555) 123-4567") == phone_match_key("555-123-4567")
    assert phone_match_key("555-123-4567 ext 12") == phone_match_key("5551234567")
    assert phone_match_key("555-0100") != phone_match_key("555-01000")


class _Partners(_Model):
    def sudo(self):
        return self

    def browse(self, rec_id=None):
        record = super().browse(rec_id)
        return type("_Browse", (), {"exists": lambda _self: record})()


def _person_bound_harness():
    orch, connection, leads, refs = _harness()
    partners = _Partners()
    orch.env["res.partner"] = partners
    person = partners.create({"name": "ERP person", "active": False})
    refs.create(
        {
            "provider": "vanillasoft",
            "external_id": "p1",
            "res_model": "res.partner",
            "res_id": person.id,
            "lead_id": False,
        }
    )
    orch._crosswalk = None
    return orch, connection, leads, refs, partners, person


def test_persisted_person_ref_blocks_the_legacy_lead_when_the_crosswalk_is_unset():
    orch, connection, leads, refs, _partners, person = _person_bound_harness()
    outcomes = _outcomes(orch)
    orch._upsert_lead(connection, _lead("p1"))
    orch._upsert_lead(connection, _lead("p1"))
    assert outcomes["unchanged"] == 2
    assert outcomes["created"] == 0
    assert orch.last_lead_outcome == "unchanged"
    assert leads.rows == {}, "an archived ERP person's binding must not fall back to a new lead"
    assert [(r.res_model, r.res_id) for r in refs.rows.values()] == [("res.partner", person.id)]


def test_duplicate_vanillasoft_ids_are_removed_before_import():
    """A second id for a person already approved on an active contact is not imported."""
    mapping = without_duplicate_contacts(
        {
            "1045036935": "127550001",
            "1179868294": "127200001",
            "584402429": "64200001",
            "585278462": "64200001",
            "1085161977": "12150001",
        }
    )
    assert mapping == {"1085161977": "12150001"}
    assert without_duplicate_contacts(None) is None


def test_inactive_contact_is_placed_on_the_active_company_not_a_lead():
    """A blank crosswalk row with a known active company does not open a lead."""
    orch, connection, leads, _refs = _harness()
    orch._crosswalk = {"572647290": ""}
    company = type("Company", (), {"id": 399})()
    person = type("Person", (), {"id": 77})()
    orch._erp_company_for_cp = lambda cp_id: (company, "")
    orch._person_on_active_company = lambda _company, _dto: person
    bound = {}

    def bind(dto, partner):
        bound["id"] = partner.id
        bound["external_id"] = dto.external_id
        orch.last_lead_outcome = "updated"
        return leads.browse()

    orch._bind_known_person = bind
    orch._upsert_lead(connection, _lead("572647290"))
    assert bound == {"id": 77, "external_id": "572647290"}
    assert leads.rows == {}
    assert orch.last_lead_outcome == "updated"


def _company_with_child(child_active: bool):
    orch, _connection, _leads, _refs = _harness()
    partners = _Partners()
    orch.env["res.partner"] = partners
    company = partners.create({"name": "Acme", "is_company": True, "active": True})
    child = partners.create({"name": "Pat Lee", "parent_id": company.id, "is_company": False, "active": child_active})
    dto = type("Dto", (), {"first_name": "Pat", "last_name": "Lee", "email": ""})()
    return orch, partners, company, child, dto


def test_an_archived_same_named_child_is_not_reused_for_the_active_company():
    orch, partners, company, archived, dto = _company_with_child(child_active=False)
    person = orch._person_on_active_company(company, dto)
    assert person.id != archived.id
    assert person.parent_id == company.id
    assert len(partners.rows) == 3


def test_an_active_same_named_child_is_reused_for_the_active_company():
    orch, partners, company, child, dto = _company_with_child(child_active=True)
    assert orch._person_on_active_company(company, dto).id == child.id
    assert len(partners.rows) == 2


def test_missing_erp_person_is_imported_as_a_crm_lead(caplog):
    """An approved id with no ERP person becomes a lead and is not bound to a partner."""
    orch, connection, leads, refs = _harness()
    orch._crosswalk = {"1085161977": "12150001"}
    orch._load_approved_crosswalk = lambda: None
    orch._resolve_orphans = lambda *_args, **_kwargs: 0
    orch._erp_person_for_ct = lambda ct_id: (
        None,
        f"ERP marker plasticos_transaction.legacy_erp_contact_{ct_id} resolved 0 rows",
    )

    class _Adapter:
        def get_contact(self, external_id):
            return _lead(external_id)

        def iter_calls_for_contact(self, _external_id):
            return []

        def iter_table_rows(self, _external_id):
            return []

    orch._build_adapter = lambda _connection: _Adapter()
    orch._apply_contact_materials = lambda *_args, **_kwargs: None
    orch._sync_tables_for_lead = lambda *_args, **_kwargs: None
    with caplog.at_level(logging.WARNING):
        lead = orch.upsert_contact_external_id(connection, "1085161977")
    assert orch.last_lead_outcome == "created"
    assert lead.id
    assert not getattr(lead, "partner_id", False)
    assert refs.rows
    assert all(row.res_model == "crm.lead" for row in refs.rows.values())
    assert orch.error_rows == []
    assert "1085161977" not in orch._crosswalk
    assert "importing as crm lead" in caplog.text
    assert "legacy_erp_contact_12150001 resolved 0 rows" in caplog.text


def test_person_ref_to_a_missing_partner_is_failed_not_recreated():
    orch, connection, leads, refs, partners, _person = _person_bound_harness()
    partners.rows.clear()
    outcomes = _outcomes(orch)
    orch._upsert_lead(connection, _lead("p1"))
    assert outcomes["failed"] == 1
    assert orch.last_lead_outcome == "failed"
    assert leads.rows == {}
    assert len(refs.rows) == 1


def test_person_ref_with_a_lead_on_another_partner_is_rejected():
    orch, connection, leads, refs, partners, _person = _person_bound_harness()
    other = partners.create({"name": "someone else"})
    leads.create({"vanillasoft_id": "p1", "partner_id": type("P", (), {"id": other.id})()})
    outcomes = _outcomes(orch)
    orch._upsert_lead(connection, _lead("p1"))
    assert outcomes["duplicate_rejected"] == 1
    assert len(leads.rows) == 1
    assert len(refs.rows) == 1


def test_approved_material_failure_rolls_back_and_is_recorded():
    orch, _connection, leads, _refs = _harness()
    lead = leads.create({"vanillasoft_id": "m1"})

    def boom(_lead, *_maps):
        leads.create({"vanillasoft_id": "partial"})
        raise RuntimeError("material constraint")

    orch._apply_resolved_approved_materials = boom
    orch._apply_approved_materials(lead, {"Materials": "HDPE"})
    assert [r.vanillasoft_id for r in leads.rows.values()] == ["m1"]
    assert orch.error_rows == [{"record_ref": "m1", "message": "material normalization failed: material constraint"}]

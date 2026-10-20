"""Approved VanillaSoft identity helpers. No Odoo runtime."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plasticos_crm_sync.adapters.vanillasoft.adapter import contact_to_canonical
from plasticos_crm_sync.services.approved_identity import (
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
)
from tests.test_crm_sync_classification import _harness, _lead, _Model, _outcomes

ROOT = Path(__file__).resolve().parents[1]
PACK_CSV = (
    ROOT
    / "Current Work - IGNORE"
    / "10-17-26"
    / "PlasticOS_CRM_ERP_Identity_GMP_STAGING_2"
    / "03_APPROVED_CONTACT_CROSSWALK.csv"
)


def _csv(rows: list[tuple[str, str]]) -> str:
    lines = ["erp_ct_id,vanillasoft_contact_id", *[f"{ct},{vs}" for ct, vs in rows], ""]
    return "\n".join(lines)


def test_pinned_crosswalk_constants():
    """Pins the constants only. It does not prove the operator file."""
    assert PINNED_SHA256 == "f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2"
    assert PINNED_VS_COUNT == 763
    assert PINNED_ERP_COUNT == 716


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
    assert len(set(mapping.values())) == PINNED_ERP_COUNT
    assert mapping["572648103"] == "2350001"
    assert mapping["1082805107"] == "192650001"
    assert "572648239" not in mapping


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

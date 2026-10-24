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


# ── approved ERP person: additive phone lines, ERP fields untouched ─────────
#
# The REAL `_upsert_lead` -> `_bind_approved_contact` -> `_add_approved_phones`
# path runs against in-memory people, phone lines and ERP markers. Synthetic data.

import types  # noqa: E402

from plasticos_crm_sync.services.approved_identity import XMLID_MODULE, xmlid_name  # noqa: E402

_ERP_PHONES = [
    {"name": "Direct", "number": "(215) 555-0101"},
    {"name": "Mobile 1", "number": "215-555-0102"},
    {"name": "Mobile 2", "number": "215.555.0103"},
    {"name": "Business", "number": "215-555-0104"},
    {"name": "Fax", "number": "215-555-0107"},
    {"name": "Home", "number": "215-555-0106", "disabled": True},
]


class _Person:
    is_company = False

    def __init__(self, rec_id, phone="", comment=False, lines=()):
        self.id = rec_id
        self.phone = phone
        self.email = "erp@example.test"
        self.name = "ERP Person"
        self.comment = comment
        self.phone_line_ids = [types.SimpleNamespace(label=label, number=number) for label, number in lines]
        self.writes: list[dict] = []

    @property
    def mobile(self):
        return next((line.number for line in self.phone_line_ids if line.label == "mobile"), "")

    def __len__(self):
        return 1

    def write(self, vals):
        self.writes.append(dict(vals))
        self.__dict__.update(vals)


class _PhoneLines:
    def __init__(self, people):
        self.people = people

    def sudo(self):
        return self

    def create(self, vals):
        line = types.SimpleNamespace(label=vals["label"], number=vals["number"])
        self.people[vals["partner_id"]].phone_line_ids.append(line)
        return line


class _Markers:
    def __init__(self, by_ct):
        self.by_ct = by_ct

    def sudo(self):
        return self

    def search(self, domain):
        name = dict((field, value) for field, _op, value in domain)["name"]
        rows = [types.SimpleNamespace(res_id=rid) for ct, rid in self.by_ct.items() if xmlid_name(ct) == name]
        return _MarkerRows(rows)


class _MarkerRows(list):
    @property
    def res_id(self):
        return self[0].res_id


class _People:
    def __init__(self, people):
        self.people = people

    def sudo(self):
        return self

    def with_context(self, **_ctx):
        return self

    def browse(self, rec_id):
        person = self.people.get(rec_id)
        return types.SimpleNamespace(exists=lambda: person if person else [])


def _approved_harness(person, *, ct="5001", vs="9001", marker=True):
    orch, connection, leads, refs = _harness()
    people = {person.id: person}
    orch.env["res.partner"] = _People(people)
    orch.env["plasticos.partner.phone"] = _PhoneLines(people)
    orch.env["ir.model.data"] = _Markers({ct: person.id} if marker else {})
    orch._crosswalk = {vs: ct}
    orch._crosswalk_ready = True
    return orch, connection, leads, refs


def _approved_dto(phones=_ERP_PHONES, note="CRM history", vs="9001"):
    return contact_to_canonical(
        {"contact_id": vs, "phone_numbers": phones, "custom_fields": [{"name": "Notes", "value": note}]}
    )


def _lines(person):
    return [(line.label, line.number) for line in person.phone_line_ids]


def test_approved_person_gets_each_number_with_its_classification():
    person = _Person(41, phone="215-555-0199")
    orch, connection, leads, _refs = _approved_harness(person)
    outcomes = _outcomes(orch)
    orch._upsert_lead(connection, _approved_dto())
    assert orch.last_lead_outcome == "updated"
    assert outcomes["updated"] == 1
    assert _lines(person) == [
        ("other", "(215) 555-0101"),
        ("mobile", "215-555-0102"),
        ("mobile", "215.555.0103"),
        ("other", "215-555-0104"),
        ("fax", "215-555-0107"),
    ], "a second genuine mobile is a mobile line; a disabled number is omitted"
    assert leads.rows == {}, "an approved contact never becomes a lead"


def test_approved_person_erp_phone_name_and_email_are_never_overwritten():
    person = _Person(42, phone="215-555-0101", lines=[("mobile", "(215) 555-0102")])
    orch, connection, _leads, _refs = _approved_harness(person)
    orch._upsert_lead(connection, _approved_dto())
    assert person.phone == "215-555-0101"
    assert (person.name, person.email) == ("ERP Person", "erp@example.test")
    assert all(set(vals) == {"comment"} for vals in person.writes), "only the additive note is written"
    assert _lines(person) == [
        ("mobile", "(215) 555-0102"),
        ("mobile", "215.555.0103"),
        ("other", "215-555-0104"),
        ("fax", "215-555-0107"),
    ], "numbers already on the ERP person, in any format, are not added again"


def test_approved_person_replay_adds_no_line_and_no_repeated_note():
    person = _Person(43, comment="<p>ERP notes</p>")
    orch, connection, _leads, _refs = _approved_harness(person)
    orch._upsert_lead(connection, _approved_dto())
    lines, comment = _lines(person), person.comment
    outcomes = _outcomes(orch)
    orch._upsert_lead(connection, _approved_dto())
    assert outcomes["unchanged"] == 1 and orch.last_lead_outcome == "unchanged"
    assert _lines(person) == lines and person.comment == comment
    assert comment_blocks(comment) == ("ERP notes", "CRM history")


def test_approved_contact_without_an_erp_person_fails_with_its_reason_and_creates_nothing():
    person = _Person(44)
    orch, connection, leads, refs = _approved_harness(person, marker=False)
    orch.outcomes = None  # the single-contact path opens no counter accumulator
    orch._upsert_lead(connection, _approved_dto())
    assert orch.last_lead_outcome == "failed"
    assert leads.rows == {} and refs.rows == {}
    assert person.phone_line_ids == [] and person.writes == []
    assert len(orch.error_rows) == 1
    row = orch.error_rows[0]
    assert row["record_ref"] == "9001"
    assert f"{XMLID_MODULE}.{xmlid_name('5001')} resolved 0 rows" in row["message"]
    assert "excluded as an inactive contact" in row["message"]


def test_record_outcome_keeps_the_reason_without_counters():
    orch, _connection, _leads, _refs = _harness()
    orch.outcomes = None
    orch._record_outcome(None, "duplicate_rejected", "9002", "multiple leads carry the source id")
    assert orch.error_rows == [{"record_ref": "9002", "message": "multiple leads carry the source id"}]
    counts = _outcomes(orch)
    orch._record_outcome(counts, "failed", "9003", "boom")
    assert counts["failed"] == 1 and orch.error_rows[-1] == {"record_ref": "9003", "message": "boom"}


def test_approved_person_keeps_each_extension_and_a_same_number_fax():
    person = _Person(45, phone="215-555-0101", lines=[("other", "555-201-0100 x101")])
    orch, connection, _leads, _refs = _approved_harness(person)
    phones = [
        {"name": "Direct", "number": "(215) 555-0101"},
        {"name": "Fax", "number": "215-555-0101"},
        {"name": "Business", "number": "555-201-0100 ext. 101"},
        {"name": "Office", "number": "555-201-0100 ext. 102"},
    ]
    orch._upsert_lead(connection, _approved_dto(phones=phones))
    assert person.phone == "215-555-0101", "the ERP phone is never overwritten"
    assert _lines(person) == [
        ("other", "555-201-0100 x101"),
        ("fax", "215-555-0101"),
        ("other", "555-201-0100 ext. 102"),
    ], "the same number as a fax and a second extension are their own lines; x101 is already there"
    lines = _lines(person)
    orch._upsert_lead(connection, _approved_dto(phones=phones))
    assert _lines(person) == lines, "a replay adds no line"


def test_approved_person_context_names_each_vanillasoft_contact_and_replays_once():
    person = _Person(46, comment="<p>ERP notes</p>")
    orch, connection, leads, refs = _approved_harness(person, vs="9001")
    orch._crosswalk["9002"] = "5001"  # two VanillaSoft contacts share one ERP person

    def dto(vs, custom):
        return contact_to_canonical({"contact_id": vs, "custom_fields": custom})

    first = dto(
        "9001",
        [
            {"name": "Notes", "value": "CRM history"},
            {"name": "Buyer/Supplier", "value": "Supplier"},
            {"name": "Last Result Code", "value": "LM"},
            {"name": "Last Call Date", "value": "2024-03-05 14:10"},
        ],
    )
    second = dto("9002", [{"name": "Buyer/Supplier", "value": "Buyer"}, {"name": "Load Ready", "value": "  "}])
    orch._upsert_lead(connection, first)
    orch._upsert_lead(connection, second)
    expected = (
        "ERP notes",
        "CRM history",
        "VanillaSoft ContactID 9001 Buyer/Supplier: Supplier",
        "VanillaSoft ContactID 9001 Last Result Code: LM",
        "VanillaSoft ContactID 9001 Last Call Date: 2024-03-05 14:10",
        "VanillaSoft ContactID 9002 Buyer/Supplier: Buyer",
    )
    assert comment_blocks(person.comment) == expected, "ERP notes stay first; a blank field adds nothing"
    assert leads.rows == {}, "an approved contact never becomes a lead"
    assert "plasticos.crm.call.event" not in orch.env, "context is a note, never a call"
    outcomes = _outcomes(orch)
    orch._upsert_lead(connection, first)
    orch._upsert_lead(connection, second)
    assert outcomes["unchanged"] == 2
    assert comment_blocks(person.comment) == expected
    assert [(r.res_model, r.external_id) for r in refs.rows.values()] == [
        ("res.partner", "9001"),
        ("res.partner", "9002"),
    ]

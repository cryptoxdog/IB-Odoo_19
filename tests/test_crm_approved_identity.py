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


def test_pinned_digest_constant_is_the_operator_file():
    assert PINNED_SHA256 == "f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2"
    assert PINNED_VS_COUNT == 763
    assert PINNED_ERP_COUNT == 716
    if PACK_CSV.is_file():
        text = PACK_CSV.read_text(encoding="utf-8")
        mapping = validate_crosswalk(text)
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

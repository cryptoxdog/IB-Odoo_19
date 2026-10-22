"""Active-contact eligibility. Blank IsActive is an exclusion, not an active row."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

from erp import mapping  # noqa: E402


def test_only_an_explicit_true_flag_is_an_eligible_contact():
    assert mapping.explicitly_active_contact("Y") is True
    assert mapping.explicitly_active_contact("1") is True
    assert mapping.explicitly_active_contact("TRUE") is True
    assert mapping.explicitly_active_contact("N") is False
    assert mapping.explicitly_active_contact("0") is False
    assert mapping.explicitly_active_contact("") is False
    assert mapping.explicitly_active_contact(None) is False
    assert mapping.explicitly_active_contact("maybe") is False


def test_an_inactive_alias_is_not_imported_with_the_active_row():
    members = [
        ("100", {"ContactNm": "Ada Lovelace", "IsActive": "Y"}),
        ("200", {"ContactNm": "Ada Lovelace", "IsActive": "N"}),
        ("300", {"ContactNm": "Blank Flag", "IsActive": ""}),
    ]
    eligible = mapping.eligible_contact_rows(members)
    assert [contact_id for contact_id, _row in eligible] == ["100"]

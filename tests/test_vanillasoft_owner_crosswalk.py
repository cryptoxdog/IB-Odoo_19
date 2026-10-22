"""Locked VanillaSoft owner email → Odoo login. No Odoo runtime."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.services.owner_crosswalk import (  # noqa: E402
    BLANK_OWNER_LOGIN,
    OWNER_LOGIN_BY_SOURCE,
    OwnerResolutionError,
    target_login,
)


def test_every_locked_source_email_has_one_destination():
    assert set(OWNER_LOGIN_BY_SOURCE) == {
        "ibeylin@ucsincny.com",
        "sales2@scrapmanagement.com",
        "ss@scrapmanagement.com",
        "aakopyan@ucsincny.com",
        "rpereira@ucsincny.com",
        "ab@ucsincny.com",
        "sa@scrapmanagement.com",
        "va@scrapmanagement.com",
        "lm@ucsincny.com",
        "sales5@scrapmanagement.com",
        "nc@scrapmanagement.com",
    }
    assert OWNER_LOGIN_BY_SOURCE["sa@scrapmanagement.com"] == "sa@scrapmanagement.com"
    assert "tw@scrapmanagement.com" not in OWNER_LOGIN_BY_SOURCE.values()


@pytest.mark.parametrize(
    ("raw", "login"),
    [
        ("ibeylin@ucsincny.com", "ib@scrapmanagement.com"),
        ("  IBEYLIN@UCSINCNY.COM ", "ib@scrapmanagement.com"),
        ("ss@scrapmanagement.com", "sales2@scrapmanagement.com"),
        ("va@scrapmanagement.com", "sales2@scrapmanagement.com"),
        ("sales5@scrapmanagement.com", "sales2@scrapmanagement.com"),
        ("nc@scrapmanagement.com", "sales2@scrapmanagement.com"),
        ("", BLANK_OWNER_LOGIN),
        ("   ", BLANK_OWNER_LOGIN),
        ("False", BLANK_OWNER_LOGIN),
        ("[blank / no owner]", BLANK_OWNER_LOGIN),
    ],
)
def test_target_login_uses_the_corrected_map(raw, login):
    assert target_login(raw) == login


def test_display_name_is_not_an_owner_match():
    with pytest.raises(OwnerResolutionError):
        target_login("CRM3 Exact Owner")

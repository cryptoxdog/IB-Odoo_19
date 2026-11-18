"""One stored format for partner phones and emails (C1 lane B).

``plasticos_facility_profile/services/contact_format.py`` is pure, so the rules
every source (ERP import, VanillaSoft, manual edit, upgrade migration) shares
are proven here without an Odoo runtime.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plasticos_facility_profile" / "services" / "contact_format.py"


def _load():
    spec = importlib.util.spec_from_file_location("contact_format_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CF = _load()


@pytest.mark.parametrize(
    "raw",
    ["732-202-9500", "7322029500", "+1 732 202 9500", "1-732-202-9500", "(732)202-9500", "  732.202.9500  "],
)
def test_nanp_numbers_share_one_format(raw):
    assert CF.format_phone(raw) == "(732) 202-9500"


def test_extension_is_kept():
    assert CF.format_phone("732-202-9500 x12") == "(732) 202-9500 x12"
    assert CF.format_phone("732-202-9500 ext. 12") == "(732) 202-9500 x12"


def test_international_number_stays_international():
    result = CF.format_phone_result("+44 20 7946 0958", "US")
    assert result.parsed
    assert result.value == "+44 20 7946 0958"


def test_international_spacing_is_normalised_without_losing_digits():
    value = CF.format_phone("+44  20 7946   0958")
    assert value.startswith("+44")
    assert "".join(ch for ch in value if ch.isdigit()) == "442079460958"
    assert "  " not in value


@pytest.mark.parametrize("raw", ["12345", "NULL", "", "call front desk"])
def test_unparseable_values_are_returned_unchanged(raw):
    result = CF.format_phone_result(raw)
    assert result.value == raw
    assert not result.parsed


def test_unparseable_value_is_only_stripped():
    assert CF.format_phone("  12345 ") == "12345"


def test_none_is_blank():
    assert CF.format_phone(None) == ""


def test_canadian_number_uses_national_format():
    assert CF.format_phone("416-555-0199", "CA") == "(416) 555-0199"
    assert CF.format_phone("+1 416 555 0199", "CA") == "(416) 555-0199"


def test_plus_one_number_is_nanp_even_for_a_non_nanp_partner():
    assert CF.format_phone("+1 732 202 9500", "GB") == "(732) 202-9500"


def test_invalid_nanp_area_code_is_left_alone():
    result = CF.format_phone_result("032-202-9500")
    assert not result.parsed
    assert result.value == "032-202-9500"


@pytest.mark.parametrize(
    "raw",
    ["732-202-9500", "732-202-9500 x12", "+44 20 7946 0958", "416-555-0199", "12345", "NULL", ""],
)
def test_phone_format_is_idempotent(raw):
    once = CF.format_phone(raw)
    assert CF.format_phone(once) == once


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a@x.com; ", "a@x.com"),
        ("A@X.com;b@y.com;;", "a@x.com, b@y.com"),
        ("a@x.com, a@x.com", "a@x.com"),
        ("not-an-email", ""),
        ("ib@scrapmanagement.com", "ib@scrapmanagement.com"),
        ("Jane Doe <Jane@Example.com>", "jane@example.com"),
        ("", ""),
        (None, ""),
    ],
)
def test_emails_share_one_format(raw, expected):
    assert CF.format_emails(raw) == expected


def test_malformed_email_entries_are_counted():
    result = CF.format_emails_result("a@x.com; nope; b@y")
    assert result.value == "a@x.com"
    assert result.dropped == 2


def test_no_domain_is_removed():
    value = CF.format_emails("buyer@scrapmanagement.com; other@example.org")
    assert value == "buyer@scrapmanagement.com, other@example.org"


@pytest.mark.parametrize("raw", ["A@X.com;b@y.com;;", "a@x.com, a@x.com", "not-an-email", "x@y.com"])
def test_email_format_is_idempotent(raw):
    once = CF.format_emails(raw)
    assert CF.format_emails(once) == once


# ── Production probe 3 tuning: country rule (operator, 2026-11-17) ──────────
def test_country_is_own_then_commercial_company_then_us():
    assert CF.country_for("CA", "US") == "CA"
    assert CF.country_for(None, "ca") == "CA"
    assert CF.country_for(False, None, "DE") == "DE"
    assert CF.country_for(None, None) == "US"


def test_commercial_company_country_formats_a_child_number():
    assert CF.format_phone("416-555-0199", CF.country_for(None, "CA")) == "(416) 555-0199"

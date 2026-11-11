"""Location is the preferred city for a pickup ZIP, and the web-lead list shows it."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import defusedxml.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "plasticos_web_lead_zip_place",
    ROOT / "plasticos_web_leads" / "zip_place.py",
)
assert _SPEC is not None and _SPEC.loader is not None
place = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(place)

_LIST_ORDER = (
    "submitted_at",
    "lead_id",
    "assigned_user_id",
    "company_name",
    "contact_name",
    "contact_phone",
    "contact_email",
    "pickup_place",
    "estimated_lbs_per_load",
    "estimated_loads_per_month",
    "decision",
    "review_status",
    "lead_source_id",
    "state",
    "frequency",
    "partner_id",
    "intake_id",
    "create_date",
)


def test_anchor_zip_resolves_and_a_broken_table_resolves_nothing():
    seller = "Miami, FL"
    postal, text, location = place.resolve_pickup(place.ANCHOR_ZIP, seller)
    assert postal == place.ANCHOR_ZIP
    assert text == seller
    assert location == place.ANCHOR_PLACE
    assert place.location_for_zip(place.ANCHOR_ZIP, {"10001": "New York, NY"}) == ""


def test_zip_plus_four_and_nine_digits_use_the_same_city():
    plus_four = place.resolve_pickup(f"{place.ANCHOR_ZIP}-1234", "")
    nine_digits = place.resolve_pickup(f"{place.ANCHOR_ZIP}1234", "")
    labeled = place.resolve_pickup(f"ZIP {place.ANCHOR_ZIP}", "")
    assert plus_four[2] == place.ANCHOR_PLACE
    assert nine_digits[2] == place.ANCHOR_PLACE
    assert labeled[2] == place.ANCHOR_PLACE
    assert plus_four[0] == f"{place.ANCHOR_ZIP}-1234"


def test_leading_zero_stays_in_the_key():
    key = place.zip_key("01001")
    assert key is not None
    assert len(key) == 5
    assert key.startswith("0")
    assert place.zip_key("1001") is None
    assert place.resolve_pickup("01001", "")[2] == place.resolve_pickup("01001-0000", "")[2]
    assert place.resolve_pickup("01001", "")[2]


def test_unknown_short_and_non_us_zips_store_the_text_and_leave_location_empty():
    unknown = "99999"
    short = "9999"
    canadian = "K1A 0A6"
    for submitted in (unknown, short, canadian):
        postal, _text, location = place.resolve_pickup(submitted, "")
        assert postal == submitted
        assert location == ""
    six_digits = "282770"
    assert place.zip_key(six_digits) is None
    assert place.resolve_pickup(six_digits, "")[2] == ""


def test_seller_text_without_a_zip_does_not_fill_location():
    seller = "Miami, FL"
    postal, text, location = place.resolve_pickup("  ", f"  {seller}  ")
    assert postal == ""
    assert text == seller
    assert location == ""


def test_raw_cognito_zip_key_fills_location():
    seller = "Miami, FL"
    raw = {"LocationOfPickUpZip": f" {place.ANCHOR_ZIP} ", "WhereIsItLocated": seller}
    postal, text, location = place.resolve_payloads({}, raw)
    assert postal == place.ANCHOR_ZIP
    assert text == seller
    assert location == place.ANCHOR_PLACE


def test_web_lead_list_puts_location_after_email_and_before_the_load_columns():
    root = ET.parse(ROOT / "plasticos_web_leads" / "views" / "web_lead_views.xml").getroot()
    names = [
        field.get("name")
        for field in root.find("record").find("field[@name='arch']").find("list")
        if field.tag == "field"
    ]
    assert tuple(names) == _LIST_ORDER
    location = root.find(".//list/field[@name='pickup_place']")
    label = "Location"
    assert location.get("string") == label

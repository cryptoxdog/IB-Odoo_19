"""Pure-Python tests for VanillaSoft client, adapter mapping, and the registry."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import (  # noqa: E402
    EXCLUDED_SOURCE_FIELDS,
    CrmAdapterError,
    source_field_key,
)
from plasticos_crm_sync.adapters.registry import LIVE_PROVIDERS, get_adapter  # noqa: E402
from plasticos_crm_sync.adapters.vanillasoft.adapter import (  # noqa: E402
    VanillaSoftAdapter,
    call_to_canonical,
    contact_to_canonical,
    vs_bool,
)
from plasticos_crm_sync.adapters.vanillasoft.client import (  # noqa: E402
    VanillaSoftClient,
    normalize_api_base,
)


def test_normalize_api_base_appends_wspubapi():
    assert normalize_api_base("https://vanillasoft.net") == "https://vanillasoft.net/WSPubAPI"
    assert normalize_api_base("https://vanillasoft.net/") == "https://vanillasoft.net/WSPubAPI"
    assert normalize_api_base("https://vanillasoft.net/WSPubAPI") == "https://vanillasoft.net/WSPubAPI"
    assert normalize_api_base("vanillasoft.net") == "https://vanillasoft.net/WSPubAPI"


def test_normalize_api_base_empty():
    with pytest.raises(CrmAdapterError):
        normalize_api_base("")


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_verify_key_success():
    opener = MagicMock()
    opener.open.return_value = _FakeResponse({"projects": [{"project_id": 139705}]})
    client = VanillaSoftClient("test-key", "https://vanillasoft.net", opener=opener)
    data = client.verify_key()
    assert data["projects"][0]["project_id"] == 139705
    req = opener.open.call_args[0][0]
    auth = req.get_header("Authorization") or req.headers.get("Authorization") or ""
    assert "APIKey=test-key" in auth


def test_get_contacts_page():
    opener = MagicMock()
    opener.open.return_value = _FakeResponse(
        {
            "contacts": [
                {
                    "contact_id": 1,
                    "company": "Acme",
                    "first_name": "A",
                    "last_name": "B",
                    "modified_date_time_utc": "2026-08-01T12:00:00Z",
                }
            ],
            "batch_end": "2026-08-01T12:00:00Z",
            "partial_fulfillment": False,
        }
    )
    client = VanillaSoftClient("k", "https://vanillasoft.net", opener=opener)
    payload = client.get_contacts(139705, "2026-07-01T00:00:00Z", limit=200)
    assert len(payload["contacts"]) == 1


def test_contact_to_canonical_and_adapter_iter():
    raw = {
        "contact_id": 42,
        "company": "Scrap Co",
        "first_name": "Pat",
        "last_name": "Lee",
        "email": "p@example.com",
        "modified_date_time_utc": "2026-08-01T10:00:00Z",
        "custom_fields": [{"name": "Lead Status", "value": "New"}],
        "phone_numbers": [{"name": "Direct", "number": "555-0100", "disabled": False}],
    }
    lead = contact_to_canonical(raw)
    assert lead.external_id == "42"
    assert lead.company == "Scrap Co"
    assert lead.phone == "555-0100"
    assert lead.lead_status_raw == "New"

    client = MagicMock()
    client.get_contacts.return_value = {
        "contacts": [raw],
        "batch_end": "2026-08-01T10:00:00Z",
        "partial_fulfillment": False,
    }
    adapter = VanillaSoftAdapter(client, 139705)
    pages = list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))
    assert len(pages) == 1
    leads, batch_end, partial = pages[0]
    assert len(leads) == 1
    assert batch_end == "2026-08-01T10:00:00Z"
    assert partial is False


def test_call_to_canonical():
    call = call_to_canonical(
        {
            "call_history_id": 9,
            "contact_id": 42,
            "call_date_time_utc": "2026-08-01T11:00:00Z",
            "duration_seconds": 120,
            "user_name": "Rep",
            "result_code": "LM",
            "comment": "hi",
        }
    )
    assert call is not None
    assert call.external_id == "9"
    assert call.contact_external_id == "42"


def test_unknown_providers_fail_closed():
    """No stub adapters exist: an unimplemented provider is an unknown one."""
    for provider in ("hubspot", "salesforce", "zoho"):
        with pytest.raises(CrmAdapterError):
            get_adapter(provider)


def test_only_vanillasoft_is_live():
    assert LIVE_PROVIDERS == {"vanillasoft"}


def test_vanillasoft_adapter_is_live():
    client = MagicMock()
    client.verify_key.return_value = {"projects": [{"project_id": 139705}]}
    adapter = get_adapter(
        "vanillasoft",
        api_key="k",
        root_endpoint="https://vanillasoft.net",
        project_id=139705,
    )
    assert adapter.live is True
    # Replace client for healthcheck
    adapter.client = client
    adapter.healthcheck()


def test_auth_failure_no_watermark_semantics():
    """HTTP 401 surfaces as CrmAdapterError (orchestrator must not advance watermark)."""
    import urllib.error

    opener = MagicMock()

    def boom(*_a, **_k):
        raise urllib.error.HTTPError(
            "https://vanillasoft.net/WSPubAPI/VerifyKey",
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b"nope"),
        )

    opener.open.side_effect = boom
    client = VanillaSoftClient("bad", "https://vanillasoft.net", opener=opener)
    with pytest.raises(CrmAdapterError, match="auth failed"):
        client.verify_key()


# ── strict provider boolean parsing ─────────────────────────────────────────
#
# Python truthiness reads every non-empty string as True, so the JSON `"false"`
# VanillaSoft sends on form-style payloads silently became True: a live contact
# archived as deleted, an enabled phone number dropped as disabled.


@pytest.mark.parametrize("value", [True, 1, "true", "True", "TRUE", "1", " 1 "])
def test_boolean_true_representations(value):
    assert vs_bool(value, field="deleted") is True


@pytest.mark.parametrize("value", [False, 0, "false", "False", "0", "", "   ", None])
def test_boolean_false_representations(value):
    assert vs_bool(value, field="deleted") is False


def test_string_false_does_not_become_true():
    """The exact inversion this parser exists to stop."""
    assert vs_bool("false", field="deleted") is False
    assert bool("false") is True, "…which plain truthiness would have got wrong"


@pytest.mark.parametrize("value", ["maybe", "yes", "no", "y", "n", "2", 7, 1.5, [], {}])
def test_malformed_boolean_fails_explicitly(value):
    """Unknown spellings raise instead of defaulting to True. `yes`/`no` are
    rejected deliberately: no payload in this repository uses them, and
    accepting a representation on speculation is how the original defect
    entered."""
    with pytest.raises(CrmAdapterError, match="unsupported boolean"):
        vs_bool(value, field="deleted")


def test_deletion_flag_uses_the_strict_parser():
    live = contact_to_canonical({"contact_id": 1, "deleted": "false"})
    gone = contact_to_canonical({"contact_id": 2, "deleted": "true"})
    absent = contact_to_canonical({"contact_id": 3})
    assert (live.deleted, gone.deleted, absent.deleted) == (False, True, False)


def test_a_malformed_deletion_flag_fails_the_contact():
    with pytest.raises(CrmAdapterError, match="deleted"):
        contact_to_canonical({"contact_id": 1, "deleted": "archived"})


def test_phone_disabled_uses_the_strict_parser():
    """`disabled: "false"` means the number is usable, not that it is disabled."""
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "phone_numbers": [{"name": "direct", "number": "555-0100", "disabled": "false"}],
        }
    )
    assert contact.phone == "555-0100"


def test_phone_marked_disabled_is_still_skipped():
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "phone_numbers": [
                {"name": "direct", "number": "555-0100", "disabled": True},
                {"name": "mobile", "number": "555-0200"},
            ],
        }
    )
    assert contact.phone == ""
    assert contact.mobile == "555-0200"


def test_unrelated_first_number_does_not_fill_phone_or_mobile():
    """Business and main numbers are not a direct line and not a mobile."""
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "phone_numbers": [
                {"name": "business", "number": "555-0300"},
                {"name": "main", "number": "555-0400"},
            ],
        }
    )
    assert contact.phone == ""
    assert contact.mobile == ""


def test_direct_and_mobile_keep_separate_meanings():
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "phone_numbers": [
                {"name": "business", "number": "555-0300"},
                {"name": "direct", "number": "555-0100"},
                {"name": "mobile 1", "number": "555-0200"},
            ],
        }
    )
    assert contact.phone == "555-0100"
    assert contact.mobile == "555-0200"


def test_observed_payload_keys_fill_only_when_the_accepted_key_is_absent():
    preferred = contact_to_canonical(
        {
            "contact_id": 1,
            "address": "1 Kept",
            "address1": "9 Ignored",
            "zip": "11111",
            "postal_code": "99999",
            "custom_fields": [
                {"name": "Lead Source", "value": "Referral"},
                {"name": "Contact Owner", "value": "Kept Owner"},
            ],
            "lead_source_name": "Ignored Source",
            "contact_owner": "Ignored Owner",
        }
    )
    assert preferred.street == "1 Kept"
    assert preferred.zip == "11111"
    assert preferred.lead_source_raw == "Referral"
    assert preferred.owner_name == "Kept Owner"

    observed = contact_to_canonical(
        {
            "contact_id": 2,
            "address1": "9 Observed",
            "postal_code": "30301",
            "lead_source_name": "Google",
            "contact_owner": "Observed Owner",
        }
    )
    assert observed.street == "9 Observed"
    assert observed.zip == "30301"
    assert observed.lead_source_raw == "Google"
    assert observed.owner_name == "Observed Owner"


def test_address_1_uses_the_same_label_family_as_address_2():
    """``Address 2`` is already an adapter alias. ``Address 1`` is that same label."""
    contact = contact_to_canonical({"contact_id": 11, "Address 1": "12 Dock St", "Address 2": "Suite 4"})
    assert contact.street == "12 Dock St"
    assert contact.street2 == "Suite 4"


def test_zip_code_is_not_mapped_until_a_payload_uses_that_key():
    """Observed zip aliases are zip, Zip, zip_code and postal_code. ``Zip Code`` is not one of them."""
    unproven = contact_to_canonical({"contact_id": 12, "Zip Code": "19103"})
    assert unproven.zip == ""
    mapped = contact_to_canonical({"contact_id": 13, "zip_code": "19104"})
    assert mapped.zip == "19104"


def test_blank_address_does_not_hide_address1_and_text_is_stripped():
    contact = contact_to_canonical(
        {
            "contact_id": 3,
            "address": "   ",
            "address1": " 9 Observed ",
            "city": " Atlanta ",
            "postal_code": " 30301 ",
        }
    )
    assert contact.street == "9 Observed"
    assert contact.city == "Atlanta"
    assert contact.zip == "30301"


# ── custom-table row identity ───────────────────────────────────────────────
#
# `(provider, table_id, external_row_id)` is a unique constraint. Deriving
# `external_row_id` from list position made row 0 of every contact collide on
# one durable key.


def _rows_for(contact_id, payload):
    client = MagicMock()
    client.get_custom_tables_list.return_value = {"custom_tables": [{"table_id": 7, "name": "Grades"}]}
    client.get_custom_table_data.return_value = payload
    return list(VanillaSoftAdapter(client, 139705).iter_table_rows(contact_id))


def test_valid_source_row_id_persists():
    rows = _rows_for("42", {"rows": [{"data_id": 9001, "grade": "HDPE"}]})
    assert [r.external_row_id for r in rows] == ["9001"]
    assert rows[0].fields == {"grade": "HDPE"}
    assert (rows[0].table_id, rows[0].contact_external_id) == ("7", "42")


def test_a_zero_source_row_id_is_a_valid_identity():
    """`0` is falsy; the old `or` chain would have replaced it with the index."""
    rows = _rows_for("42", {"rows": [{"data_id": 0, "grade": "PET"}]})
    assert [r.external_row_id for r in rows] == ["0"]


@pytest.mark.parametrize("row", [{"grade": "HDPE"}, {"data_id": None, "grade": "HDPE"}, {"data_id": "  "}])
def test_missing_source_row_id_is_not_replaced_with_the_index(row):
    assert _rows_for("42", {"rows": [row]}) == []


def test_rows_from_two_contacts_cannot_collide_via_array_position():
    """Both contacts' first row lacks an id. Under the index fallback both
    became `(vanillasoft, 7, '0')` — one constraint key, two contacts, and each
    import silently overwrote the other's enrichment."""
    payload = {"rows": [{"grade": "HDPE"}]}
    assert _rows_for("42", payload) == []
    assert _rows_for("77", payload) == []


def test_excluded_source_columns_never_enter_a_custom_table_row():
    rows = _rows_for(
        "42",
        {
            "rows": [
                {
                    "data_id": 9001,
                    "Material": "HDPE Drums",
                    "Notes": "Load Ready is mentioned in ordinary notes",
                    "FOB/FAS (HDPE)": "EXCL-FOB-HDPE",
                    "Melt (LDPE)": "EXCL-MELT",
                    "Density (PP)": "EXCL-DENSITY",
                    "Equipment": "EXCL-EQUIPMENT",
                    "Price Quoted (MRP)": "EXCL-PRICE",
                    "Load Ready": "EXCL-LOAD",
                    "NAICS Code  Description": "EXCL-NAICS",
                }
            ]
        },
    )
    assert rows[0].fields["Material"] == "HDPE Drums"
    assert rows[0].fields["Notes"] == "Load Ready is mentioned in ordinary notes"
    blob = " ".join(value for key, value in rows[0].fields.items() if key != "Notes")
    for token in (
        "EXCL-FOB-HDPE",
        "EXCL-MELT",
        "EXCL-DENSITY",
        "EXCL-EQUIPMENT",
        "EXCL-PRICE",
        "EXCL-LOAD",
        "EXCL-NAICS",
    ):
        assert token not in blob


# Exact v1.4 EXCLUDE_NO_ODOO_PERSISTENCE labels. The double space in the NAICS
# description is the workbook spelling.
_EXCLUDED_BY_SPEC = (
    "Load Ready",
    "ClosedFlag",
    "Team",
    "Call Back Date",
    "Call Back Time",
    "Scheduled Call User",
    "SIC Code",
    "SIC Code Description",
    "NAICS Code",
    "NAICS Code  Description",
    "Sales Volume Range",
    "Sales Volume",
    "Employees",
    "Square Footage",
    "Fleet Size",
    "Product (MFR)",
    "Truck Size (E)",
    "Equipment",
    "Price Quoted (MRP)",
    "FOB/FAS (MRP)",
    "Price Quoted (PPS)",
    "FOB/FAS (PPS)",
    "Melt (LDPE)",
    "Density (LDPE)",
    "Price Quoted (LDPE)",
    "FOB/FAS (LDPE)",
    "Melt (HDPE)",
    "Density (HDPE)",
    "Load Ready (HDPE)",
    "Price Quoted (HDPE)",
    "FOB/FAS (HDPE)",
    "Melt (PP)",
    "Density (PP)",
    "Price Quoted (PP)",
    "FOB/FAS (PP)",
)


def test_excluded_labels_match_the_v1_4_matrix():
    assert len(_EXCLUDED_BY_SPEC) == 35
    assert tuple(EXCLUDED_SOURCE_FIELDS) == _EXCLUDED_BY_SPEC
    assert len({source_field_key(name) for name in _EXCLUDED_BY_SPEC}) == 35


def test_an_identified_row_still_persists_alongside_a_skipped_one():
    """Skipping is per row: one unusable row must not drop its siblings."""
    rows = _rows_for("42", {"rows": [{"grade": "HDPE"}, {"data_id": 9002, "grade": "PP"}]})
    assert [r.external_row_id for r in rows] == ["9002"]


# ── phone_numbers[] fidelity: one reading, every enabled number kept ─────────

_ALL_PHONES = [
    {"name": "Direct", "number": "(215) 555-0101"},
    {"name": "Mobile 1", "number": "215-555-0102", "disabled": "false"},
    {"name": "Mobile 2", "number": "215.555.0103", "disabled": 0},
    {"name": "Business", "number": "215-555-0104"},
    {"name": "Office", "number": "215-555-0105"},
    {"name": "Home", "number": "215-555-0106"},
    {"name": "Fax", "number": "215-555-0107"},
]


def _entries(contact):
    return [(entry.label, entry.number, entry.kind) for entry in contact.phone_entries]


def test_every_enabled_number_keeps_its_source_label_and_classification():
    contact = contact_to_canonical({"contact_id": 7, "phone_numbers": _ALL_PHONES})
    assert contact.phone == "(215) 555-0101"
    assert contact.mobile == "215-555-0102"
    assert _entries(contact) == [
        ("Direct", "(215) 555-0101", "other"),
        ("Mobile 1", "215-555-0102", "mobile"),
        ("Mobile 2", "215.555.0103", "mobile"),
        ("Business", "215-555-0104", "other"),
        ("Office", "215-555-0105", "other"),
        ("Home", "215-555-0106", "other"),
        ("Fax", "215-555-0107", "fax"),
    ]
    assert contact.phone_numbers == tuple(number for _label, number, _kind in _entries(contact))
    assert contact.mobile_numbers == ("215-555-0102", "215.555.0103")


def test_disabled_true_is_omitted_and_disabled_false_is_kept():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone_numbers": [
                {"name": "Mobile 1", "number": "215-555-0102", "disabled": "true"},
                {"name": "Mobile 2", "number": "215-555-0103", "Disabled": False},
            ],
        }
    )
    assert _entries(contact) == [("Mobile 2", "215-555-0103", "mobile")]
    assert contact.mobile == "215-555-0103"


@pytest.mark.parametrize("value", ["maybe", "yes", 2])
def test_an_unknown_disabled_spelling_is_a_reported_source_error(value):
    with pytest.raises(CrmAdapterError, match=r"contact 7 phone_numbers\[1\]\.disabled"):
        contact_to_canonical(
            {
                "contact_id": 7,
                "phone_numbers": [
                    {"name": "Direct", "number": "215-555-0101"},
                    {"name": "Mobile 1", "number": "215-555-0102", "disabled": value},
                ],
            }
        )


def test_mobile_two_alone_is_kept_as_the_mobile():
    contact = contact_to_canonical({"contact_id": 7, "phone_numbers": [{"name": "Mobile 2", "number": "215-555-0103"}]})
    assert contact.mobile == "215-555-0103"
    assert _entries(contact) == [("Mobile 2", "215-555-0103", "mobile")]


def test_two_distinct_mobiles_are_both_kept():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone_numbers": [
                {"name": "Mobile 1", "number": "215-555-0102"},
                {"name": "Mobile 2", "number": "215-555-0103"},
            ],
        }
    )
    assert contact.mobile == "215-555-0102"
    assert contact.mobile_numbers == ("215-555-0102", "215-555-0103")


def test_formatting_variants_of_one_number_are_one_entry():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone_numbers": [
                {"name": "Direct", "number": "(215) 555-0101"},
                {"name": "Business", "number": "+1 215.555.0101"},
                {"name": "Office", "number": "215-555-0101 ext. 4"},
                {"name": "Work", "number": "215 555 0101 x4"},
            ],
        }
    )
    assert _entries(contact) == [
        ("Direct", "(215) 555-0101", "other"),
        ("Office", "215-555-0101 ext. 4", "other"),
    ], "an extension is its own line; a formatting variant of one line is not"


def test_distinct_extensions_of_one_number_stay_two_lines():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone_numbers": [
                {"name": "Direct", "number": "555-201-0100 ext. 101"},
                {"name": "Business", "number": "555-201-0100 ext. 102"},
            ],
        }
    )
    assert _entries(contact) == [
        ("Direct", "555-201-0100 ext. 101", "other"),
        ("Business", "555-201-0100 ext. 102", "other"),
    ]


def test_one_number_given_as_direct_and_fax_keeps_both_classifications():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone_numbers": [
                {"name": "Direct", "number": "215-555-0101"},
                {"name": "Fax", "number": "(215) 555-0101"},
            ],
        }
    )
    assert _entries(contact) == [("Direct", "215-555-0101", "other"), ("Fax", "(215) 555-0101", "fax")]


def test_a_number_disabled_in_the_list_never_returns_through_the_top_level_fallback():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone": "+1 (215) 555-0101",
            "Direct": "215-555-0199",
            "mobile": "215.555.0102",
            "phone_numbers": [
                {"name": "Direct", "number": "215-555-0101", "disabled": True},
                {"name": "Mobile 1", "number": "215-555-0102", "disabled": "1"},
            ],
        }
    )
    assert contact.phone == "215-555-0199", "the next top-level value that the list did not disable"
    assert contact.mobile == ""
    assert contact.phone_entries == ()


def test_the_top_level_number_is_still_a_fallback_when_the_list_has_none():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone": "215-555-0101",
            "mobile": "215-555-0102",
            "phone_numbers": [{"name": "Fax", "number": "215-555-0107"}],
        }
    )
    assert (contact.phone, contact.mobile) == ("215-555-0101", "215-555-0102")


def test_address2_fills_street2_only_when_the_earlier_aliases_are_blank():
    filled = contact_to_canonical({"contact_id": 1, "address_2": "Suite A", "address2": "Suite B"})
    assert filled.street2 == "Suite A"
    alias = contact_to_canonical({"contact_id": 1, "Address 2": "Suite C", "address2": "Suite D"})
    assert alias.street2 == "Suite C"
    only = contact_to_canonical({"contact_id": 1, "address2": "Dock 4"})
    assert only.street2 == "Dock 4"


def test_a_separate_extension_and_country_code_fold_into_the_existing_number():
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "phone_numbers": [
                {"name": "Direct", "number": "215-555-0100", "extension": "101", "country_code": "1"},
                {"name": "Office", "number": "215-555-0100", "Extension": "102", "CountryCode": "1"},
            ],
        }
    )
    assert _entries(contact) == [
        ("Direct", "+1 215-555-0100 x101", "other"),
        ("Office", "+1 215-555-0100 x102", "other"),
    ]


def test_a_contradictory_extension_is_dropped_and_a_prefixed_number_is_left_alone():
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "phone_numbers": [
                {"name": "Direct", "number": "215-555-0100 x101", "extension": "102"},
                {"name": "Office", "number": "+1 215-555-0101", "country_code": "1"},
                {"name": "Home", "number": "12155550102", "country_code": "1"},
            ],
        }
    )
    assert _entries(contact) == [
        ("Office", "+1 215-555-0101", "other"),
        ("Home", "12155550102", "other"),
    ]


def test_a_disabled_number_with_a_separate_extension_does_not_return():
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "phone": "215-555-0100",
            "phone_numbers": [{"name": "Direct", "number": "215-555-0100", "extension": "101", "disabled": True}],
        }
    )
    assert contact.phone == ""
    assert contact.phone_entries == ()


def test_website_and_title_are_canonical_and_leave_the_address_country_alone():
    contact = contact_to_canonical(
        {
            "contact_id": 1,
            "Website": "https://example.test",
            "title": "Buyer",
            "country": "USA",
            "phone_numbers": [{"name": "Direct", "number": "215-555-0100", "country_code": "44"}],
        }
    )
    assert (contact.website, contact.job_title, contact.country_code) == ("https://example.test", "Buyer", "USA")
    assert contact.phone_entries[0].number == "+44 215-555-0100"


def test_the_list_wins_over_the_top_level_number():
    contact = contact_to_canonical(
        {
            "contact_id": 7,
            "phone": "215-555-0199",
            "phone_numbers": [{"name": "Direct", "number": "215-555-0101"}],
        }
    )
    assert contact.phone == "215-555-0101"

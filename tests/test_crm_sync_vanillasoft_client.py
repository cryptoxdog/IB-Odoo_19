"""Pure-Python tests for VanillaSoft client, adapter mapping, and stub registry."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import CrmAdapterError, CrmAdapterStubError  # noqa: E402
from plasticos_crm_sync.adapters.registry import ensure_live_or_raise, get_adapter  # noqa: E402
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


def test_stub_adapters_raise():
    for provider in ("hubspot", "salesforce", "zoho"):
        adapter = get_adapter(provider)
        assert adapter.live is False
        with pytest.raises(CrmAdapterStubError):
            adapter.healthcheck()
        with pytest.raises(CrmAdapterStubError):
            ensure_live_or_raise(adapter)


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
    ensure_live_or_raise(adapter)
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
    assert contact.phone != "555-0100"
    assert contact.mobile == "555-0200"


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


def test_an_identified_row_still_persists_alongside_a_skipped_one():
    """Skipping is per row: one unusable row must not drop its siblings."""
    rows = _rows_for("42", {"rows": [{"grade": "HDPE"}, {"data_id": 9002, "grade": "PP"}]})
    assert [r.external_row_id for r in rows] == ["9002"]

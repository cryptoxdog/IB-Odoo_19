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

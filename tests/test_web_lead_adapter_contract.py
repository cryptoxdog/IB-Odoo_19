"""Conformance contract for every registered inbound web-lead adapter."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plasticos_web_leads"

package = sys.modules.setdefault("plasticos_web_leads", types.ModuleType("plasticos_web_leads"))
package.__path__ = [str(PACKAGE_ROOT)]

from plasticos_web_leads.adapters.base import (  # noqa: E402
    EVENT_SUBMITTED,
    PACKET_SCHEMA_VERSION,
    InboundRequest,
    WebLeadAdapter,
    packet_to_dict,
)
from plasticos_web_leads.adapters.registry import _ADAPTERS, get_adapter, registered_provider_keys  # noqa: E402


def _request(*, headers=None, query=None, path_token=None) -> InboundRequest:
    return InboundRequest(headers=headers or {}, query=query or {}, raw_body=b"{}", path_token=path_token)


@pytest.mark.parametrize("provider_key, adapter", list(_ADAPTERS.items()))
def test_registered_adapter_conforms_to_the_port(provider_key, adapter):
    assert isinstance(adapter, WebLeadAdapter)
    assert adapter.provider_key == provider_key
    assert adapter.attachment_allowed_hosts
    assert all(host == host.lower() and "://" not in host for host in adapter.attachment_allowed_hosts)

    packet = adapter.to_packet(type(adapter).sample_payload())
    assert packet.schema_version == PACKET_SCHEMA_VERSION
    assert packet.provider == provider_key
    assert packet.idempotency_key
    assert packet.provider_external_id
    for attachment in packet.attachments:
        assert attachment.source_id
        assert attachment.source_url.startswith("https://")

    canonical = json.dumps(packet_to_dict(packet, omit_raw_payload=True))
    assert "source_url" not in canonical

    event = adapter.classify_event(type(adapter).sample_payload())
    assert event.kind == EVENT_SUBMITTED
    assert event.provider_external_id == packet.provider_external_id

    secret = "port-contract-secret"
    assert adapter.authenticate(_request(query={"access_token": secret}), secret=secret)
    assert adapter.authenticate(_request(headers={"Authorization": f"Bearer {secret}"}), secret=secret)
    assert not adapter.authenticate(_request(query={"access_token": "wrong"}), secret=secret)
    assert not adapter.authenticate(_request(), secret=secret)
    assert not adapter.authenticate(_request(query={"access_token": secret}), secret="")


def test_registry_lists_exactly_its_adapters_and_fails_closed():
    assert registered_provider_keys() == tuple(_ADAPTERS)
    with pytest.raises(ValueError, match="Unsupported"):
        get_adapter("unknown")

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


# ---------------------------------------------------------------------------
# Authentication is owned by the adapter; the controller never pre-empts it
# ---------------------------------------------------------------------------
import ast  # noqa: E402
import hashlib  # noqa: E402
import hmac  # noqa: E402

from plasticos_web_leads.adapters.base import InboundEvent  # noqa: E402
from plasticos_web_leads.adapters.cognito import CognitoFormsAdapter  # noqa: E402

CONTROLLER = PACKAGE_ROOT / "controllers" / "web_lead_api.py"
MODEL = PACKAGE_ROOT / "models" / "web_lead.py"
CONFIG_MODEL = PACKAGE_ROOT / "models" / "web_lead_config.py"
MIGRATION = PACKAGE_ROOT / "migrations" / "19.0.2.8.0" / "post-migrate.py"


class _BodySigningAdapter(WebLeadAdapter):
    """A provider that signs the body and never presents a bearer token."""

    provider_key = "signed-test"
    attachment_allowed_hosts = ("example.test",)

    def to_packet(self, payload):  # pragma: no cover - not exercised here
        raise NotImplementedError

    def classify_event(self, payload):  # pragma: no cover - not exercised here
        return InboundEvent(provider=self.provider_key, kind=EVENT_SUBMITTED, provider_external_id="1", payload=payload)

    @classmethod
    def sample_payload(cls):  # pragma: no cover - not exercised here
        return {}

    def authenticate(self, request: InboundRequest, *, secret: str) -> bool:
        expected = hmac.new(secret.encode(), request.raw_body, hashlib.sha256).hexdigest()
        presented = request.headers.get("X-Signature", "")
        return bool(secret) and hmac.compare_digest(presented, expected)


def test_a_body_signing_adapter_authenticates_without_any_presented_token():
    adapter = _BodySigningAdapter()
    secret = "shared-signing-secret"
    body = b'{"Entry": {"Number": "1"}}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    signed = InboundRequest(headers={"X-Signature": signature}, query={}, raw_body=body)
    assert adapter.presented_tokens(signed) == (), "the signing provider presents no bearer token"
    assert adapter.authenticate(signed, secret=secret)
    assert not adapter.authenticate(InboundRequest(headers={}, query={}, raw_body=body), secret=secret)
    assert not adapter.authenticate(signed, secret="other")


def test_controller_reaches_adapter_authenticate_without_rejecting_on_missing_tokens_first():
    source = CONTROLLER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    authenticate = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_authenticate"
    )
    body = ast.get_source_segment(source, authenticate)
    assert "adapter.authenticate(inbound, secret=" in body
    assert "Missing API token" not in body
    # No early return may depend on presented_tokens before the adapter decides.
    first_adapter_call = body.index("adapter.authenticate(")
    before = body[:first_adapter_call]
    assert "presented_tokens" not in before, "the controller must not gate on bearer tokens before the adapter"
    # The raw body reaches the adapter so a signing provider can verify it.
    assert "raw_body=httprequest.get_data()" in source


def test_cognito_relies_on_the_port_token_check_and_declares_no_signature():
    adapter = CognitoFormsAdapter()
    assert type(adapter).authenticate is WebLeadAdapter.authenticate


# ---------------------------------------------------------------------------
# Rejected deliveries are idempotent on the provider's stable identity
# ---------------------------------------------------------------------------
def test_rejected_inbound_dedupes_on_provider_identity_in_its_own_namespace():
    source = MODEL.read_text(encoding="utf-8")
    assert 'REJECTED_LEAD_PREFIX = "REJ-"' in source
    tree = ast.parse(source)
    record = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "record_rejected_inbound"
    )
    body = ast.get_source_segment(source, record)
    assert "_rejected_external_id" in body
    assert "_find_existing_lead(lead_id)" in body
    assert "_create_or_replay(vals)" in body, "a concurrent repeat must converge on one rejection row"
    assert '"provider_external_id": external_id or False' in body
    helper = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_rejected_external_id"
    )
    assert "classify_event" in ast.get_source_segment(source, helper)


# ---------------------------------------------------------------------------
# Default-provider field: declaration, backfill, fallback
# ---------------------------------------------------------------------------
def _field_keywords(tree: ast.Module, field_name: str) -> dict:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == field_name for t in node.targets):
            call = node.value
            assert isinstance(call, ast.Call)
            return {kw.arg: kw.value for kw in call.keywords}
    raise AssertionError(f"{field_name} is not declared")


def test_default_provider_field_is_required_and_defaults_to_cognito():
    tree = ast.parse(CONFIG_MODEL.read_text(encoding="utf-8"))
    keywords = _field_keywords(tree, "inbound_default_provider_key")
    assert ast.literal_eval(keywords["default"]) == "cognito"
    assert ast.literal_eval(keywords["required"]) is True
    assert "cognito" in registered_provider_keys()


def test_default_provider_migration_backfills_leads_and_config():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "UPDATE plasticos_web_lead" in source and "SET provider_key = 'cognito'" in source
    assert "WHERE provider_key IS NULL" in source
    assert "UPDATE plasticos_web_lead_config" in source
    assert "COALESCE(NULLIF(inbound_default_provider_key, ''), 'cognito')" in source


def test_attachment_policy_falls_back_to_the_configured_default_provider():
    source = MODEL.read_text(encoding="utf-8")
    tree = ast.parse(source)
    hosts = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_attachment_allowed_hosts"
    )
    body = ast.get_source_segment(source, hosts)
    assert "self.provider_key or" in body
    assert "config.inbound_default_provider_key" in body
    assert '"cognito"' not in body, "the fallback reads the configured default, never a hard-coded provider"

"""Canonical Gate contract: Odoo emits EnrichRequest, consumes EnrichResponse.

The rail this pins:

    Odoo build_converge_request
      -> Gate_SDK create_transport_packet (action="converge")
      -> Constellation.Gate
      -> EIE canonical EnrichRequest handler
      -> EnrichResponse
      -> Odoo map_converge_response

Odoo is a domain producer/consumer on that rail. It owns neither transport nor
routing, and it must not grow a second converge dialect beside the canonical
one. The negative tests below are architecture regression guards: each names a
specific way the contract previously drifted, or could drift back.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_builders import (  # noqa: E402
    build_converge_request,
    build_odoo_context,
    build_operation_id,
)
from plasticos_gate.services.gate_config import (  # noqa: E402
    DEFAULT_GATE_TIMEOUT_SECONDS,
    MAX_GATE_TIMEOUT_SECONDS,
    GateIntegrationError,
    resolve_gate_timeout_seconds,
)
from plasticos_gate.services.gate_mappers import (  # noqa: E402
    map_converge_response,
    partner_writeback_from_converge,
)

PARTNER_ID = 55
RUN_ID = 7
ENTITY_REF = f"res.partner:{PARTNER_ID}"


class _FakePartner:
    _fields: dict = {}

    def __init__(self, partner_id: int):
        self.id = partner_id


class _FakeRun:
    _name = "plasticos.enrichment.run"
    source_ids = ()

    def __init__(self, run_id: int, partner: _FakePartner):
        self.id = run_id
        self.partner_id = partner


class _FakeEnv:
    def __init__(self, db_name: str = "plasticos"):
        self.company = type("C", (), {"id": 1})()
        self.user = type("U", (), {"id": 2})()
        self.cr = type("R", (), {"dbname": db_name})()


def _request():
    return build_converge_request(_FakeEnv(), _FakeRun(RUN_ID, _FakePartner(PARTNER_ID)))


def _payload():
    return _request().to_dict()


# ── PATCH 8 — the exact request the live builder emits ─────────────────────
#
# Source: plasticos_gate/services/gate_builders.py::build_converge_request
#         -> plasticos_gate/services/gate_contracts.py::ConvergeRequest.to_dict
# Semantically identical to the fixture in the EIE repo at
# tests/unit/test_odoo_cross_repo_contract.py::_odoo_builder_payload — kept in
# sync by shape, never by a runtime dependency between the two repositories.


def test_payload_is_enrich_request_shaped():
    payload = _payload()
    assert set(payload) >= {"entity", "object_type", "objective", "max_variations"}
    assert isinstance(payload["entity"], dict)
    assert isinstance(payload["max_variations"], int)


def test_canonical_identity_is_on_the_entity():
    entity = _payload()["entity"]
    assert entity["id"] == ENTITY_REF


def test_compatibility_alias_carries_the_same_value():
    entity = _payload()["entity"]
    assert entity["_odoo_entity_id"] == entity["id"]


def test_odoo_context_travels_as_metadata():
    odoo = _payload()["odoo"]
    assert odoo["model"] == "plasticos.enrichment.run"
    assert odoo["record_id"] == RUN_ID
    assert odoo["correlation_id"] == f"plasticos.enrichment.run:{RUN_ID}"


def test_kb_context_declares_the_domain_explicitly():
    """EIE resolves the KB domain `domain_id` -> `domain` -> `kb_context` ->
    `object_type`. Relying on object_type is the last fallback and works only
    because Odoo happens to carry the domain there; kb_context states it."""
    payload = _payload()
    assert payload["kb_context"] == "plasticos"
    assert payload["kb_context"] == payload["object_type"]


def test_payload_validates_as_a_canonical_enrich_request():
    """EIE's canonical branch does `EnrichRequest.model_validate(payload)`, so
    the payload must carry only EnrichRequest-legal keys plus the odoo context."""
    enrich_request_fields = {
        "entity",
        "object_type",
        "objective",
        "max_variations",
        "kb_context",
        "idempotency_key",
        "schema",
    }
    extra = set(_payload()) - enrich_request_fields - {"odoo"}
    assert not extra, f"payload carries non-EnrichRequest keys: {sorted(extra)}"


def test_mapper_keeps_fields_eie_no_longer_truncates():
    """The canonical branch returns EnrichResponse untruncated — the old adapter
    clipped `fields` to the eight partner keys. Odoo keeps the full set for
    audit and enforces its allowlist only at the writeback boundary."""
    resp = map_converge_response(_eie_response(fields={"website": "https://a.example", "polymer_type": "HDPE"}))
    assert resp.final_fields == {"website": "https://a.example", "polymer_type": "HDPE"}
    assert partner_writeback_from_converge(resp) == {"website": "https://a.example"}


# ── PATCH 11 — negative: no drift into the alternate adapter dialect ───────


def test_request_does_not_emit_entity_snapshot():
    """`entity_snapshot` belongs to EIE's alternate adapter dialect, not here."""
    assert "entity_snapshot" not in _payload()


def test_request_does_not_emit_a_top_level_entity_id():
    """A top-level entity_id would fork the canonical EnrichRequest contract."""
    assert "entity_id" not in _payload()


def test_request_does_not_emit_response_side_keys():
    payload = _payload()
    for forbidden in ("status", "final_fields", "writeback"):
        assert forbidden not in payload


def test_gate_client_holds_no_eie_peer_address():
    """O2 — Odoo addresses Gate, never EIE. Routing is Gate's job."""
    for name in ("gate_client.py", "gate_config.py", "gate_builders.py"):
        lowered = (ROOT / "plasticos_gate" / "services" / name).read_text(encoding="utf-8").lower()
        for probe in ("enrichment.inference", "eie_url", "eie_endpoint", "/v1/execute", "eie.", ":8000"):
            assert probe not in lowered, f"{name} addresses a peer directly: {probe}"


def test_gate_destination_is_sdk_owned_not_set_in_odoo():
    """Pack ADR-002/ADR-016 — Gate-only egress is enforced by the SDK, not by Odoo.

    This replaces an earlier assertion that Odoo *sets* ``destination_node="gate"``
    on the packet. That test fossilized the abstraction leak: it made
    Odoo-side routing policy a requirement. The SDK already defaults
    ``destination_node`` to ``"gate"``, and ``validate_outbound_gate_packet``
    rejects any other destination using ``GateClientConfig.allowed_gate_destination``.
    So the correct assertion is the inverse — Odoo must NOT name the
    destination, and the config must pin it.
    """
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "destination_node=" not in src, (
        "gate_client.py names a packet destination — routing is Gate_SDK's "
        "authority (pack ADR-002). Let the SDK default apply."
    )
    config_src = (ROOT / "plasticos_gate" / "services" / "gate_config.py").read_text(encoding="utf-8")
    assert 'allowed_gate_destination="gate"' in config_src, (
        "GateClientConfig must pin allowed_gate_destination='gate' so the SDK "
        "enforces Gate-only egress on Odoo's behalf."
    )


def test_odoo_does_not_restate_sdk_transport_defaults():
    """Pack ADR-007 — the adapter supplies business inputs, not transport policy."""
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    for policy_arg in ("classification=", "priority=", "retention_days=", "expires_at="):
        assert policy_arg not in src, (
            f"gate_client.py sets transport policy {policy_arg!r}; Gate_SDK owns "
            "packet defaults (pack ADR-001/ADR-007)."
        )


# ── PATCH 9 — canonical EnrichResponse consumption ────────────────────────


def _eie_response(**overrides):
    base = {
        "state": "completed",
        "fields": {"website": "https://acme.example", "phone": "555-0100"},
        "pass_count": 2,
        "tokens_used": 1200,
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def test_mapper_accepts_canonical_state_fields_response():
    resp = map_converge_response(_eie_response())
    assert resp.state == "completed"
    assert resp.status == "ok"  # derived from state, not read off the wire
    assert resp.final_fields == {"website": "https://acme.example", "phone": "555-0100"}


def test_mapper_does_not_require_status_final_fields_or_writeback():
    """A response carrying none of the obsolete envelope still maps cleanly."""
    payload = _eie_response()
    for absent in ("status", "final_fields", "writeback"):
        assert absent not in payload
    assert map_converge_response(payload).status == "ok"


def test_mapper_fails_closed_without_an_explicit_completed_state():
    for payload in ({}, {"state": ""}, {"fields": {"website": "x"}}):
        assert map_converge_response(payload).status != "ok"


def test_mapper_reports_failure_reason_over_state():
    resp = map_converge_response(_eie_response(state="failed", failure_reason="provider timeout"))
    assert resp.status == "provider timeout"


# ── PATCH 7 — writeback safety survives the contract repair ────────────────


def test_writeback_proposal_is_allowlisted():
    resp = map_converge_response(_eie_response(fields={"website": "https://a.example", "vat": "SECRET", "id": 9}))
    proposal = partner_writeback_from_converge(resp)
    assert proposal == {"website": "https://a.example"}


def test_writeback_proposal_drops_empty_values():
    resp = map_converge_response(_eie_response(fields={"website": "", "phone": None, "city": "NC"}))
    assert partner_writeback_from_converge(resp) == {"city": "NC"}


# ── ADR-006 — one logical operation identity across replay boundaries ─────


def _ctx(record_id: int = RUN_ID, db_name: str = "plasticos"):
    return build_odoo_context(_FakeEnv(db_name), model="plasticos.enrichment.run", record_id=record_id).to_dict()


def test_operation_id_is_stable_for_a_retry_of_the_same_run():
    """ADR-006 required behavior: same durable run + retry -> same operation ID."""
    assert build_operation_id(_ctx()) == build_operation_id(_ctx())


def test_operation_id_does_not_depend_on_the_payload():
    """The identity is the RUN, not a serialization of its payload.

    This replaces earlier tests asserting the opposite — that editing the
    partner, or reordering dict keys, changed the key. That was ADR-006's
    rejected Option B: keying on a payload digest makes "same operation" a
    serialization fact rather than a business fact, and leaves the transport
    key uncorrelatable with the durable run it belongs to. ``build_operation_id``
    accepts no payload at all, which makes the property structural rather than
    merely observed.
    """
    import inspect

    from plasticos_gate.services.gate_builders import build_operation_id as _fn

    assert "payload" not in set(inspect.signature(_fn).parameters)


def test_operation_id_differs_across_runs():
    assert build_operation_id(_ctx(7)) != build_operation_id(_ctx(8))


def test_operation_id_is_database_scoped():
    assert build_operation_id(_ctx(db_name="prod")) != build_operation_id(_ctx(db_name="staging"))


def test_operation_id_carries_no_timestamp_or_randomness():
    assert len({build_operation_id(_ctx()) for _ in range(5)}) == 1


def test_operation_id_is_none_without_run_identity():
    assert build_operation_id({}) is None


def test_operation_id_uses_the_adr_006_semantic_form():
    """odoo:<family>:<db>:<model>:<record-id> — no digest segment."""
    key = build_operation_id(_ctx())
    assert key == f"odoo:enrichment:plasticos:plasticos.enrichment.run:{RUN_ID}"


def test_one_identity_reaches_both_replay_boundaries():
    """ADR-006 — the domain field and the transport header carry the SAME value.

    The request builder generates it once; the consumer hands
    ``request.idempotency_key`` to the transport rather than deriving a second
    value. ``EnrichRequest.idempotency_key`` is a canonical EIE field, so
    carrying it in the payload is domain propagation, not a new dialect.
    """
    request = _request()
    expected = build_operation_id(request.odoo)
    assert expected is not None
    assert request.idempotency_key == expected
    assert request.to_dict()["idempotency_key"] == expected


def test_consumer_does_not_derive_a_second_operation_identity():
    """The enrichment consumer must reuse request.idempotency_key, not recompute one."""
    src = (ROOT / "plasticos_enrichment" / "models" / "enrichment_run.py").read_text(encoding="utf-8")
    assert "idempotency_key=request.idempotency_key" in src
    assert "build_idempotency_key" not in src, (
        "the payload-digest key builder is retired; one identity is generated by build_converge_request (ADR-006)"
    )


# ── PATCH 10 — Gate_SDK owns the packet ───────────────────────────────────
#
# The real SDK-invocation proof (Odoo domain call -> installed Gate_SDK ->
# packet/client boundary, network seam patched only) lives in
# tests/test_gate_sdk_invocation.py. An earlier test here reconstructed the
# create_transport_packet argument list by hand, which asserted nothing about
# the adapter: it duplicated the adapter's own code and so could not detect the
# adapter drifting away from it.


# ── PATCH 5 — the caller budget is one value, and it has a ceiling ────────


class _FakeIcp:
    """Minimal ir.config_parameter stand-in: sudo() -> self, get_param -> dict."""

    def __init__(self, params: dict[str, str]):
        self._params = params

    def sudo(self):
        return self

    def get_param(self, key, default=None):
        return self._params.get(key, default)


class _TimeoutEnv:
    def __init__(self, raw=None):
        params = {} if raw is None else {"plasticos.gate.timeout_seconds": raw}
        self._icp = _FakeIcp(params)

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        return self._icp


def test_caller_budget_falls_back_to_thirty_seconds_when_unset():
    assert resolve_gate_timeout_seconds(_TimeoutEnv()) == DEFAULT_GATE_TIMEOUT_SECONDS
    assert DEFAULT_GATE_TIMEOUT_SECONDS == 30.0


def test_caller_budget_accepts_the_seeded_default():
    assert resolve_gate_timeout_seconds(_TimeoutEnv("30")) == 30.0


def test_caller_budget_accepts_the_ceiling_exactly():
    assert resolve_gate_timeout_seconds(_TimeoutEnv(str(MAX_GATE_TIMEOUT_SECONDS))) == MAX_GATE_TIMEOUT_SECONDS


def test_caller_budget_accepts_a_shorter_budget():
    """Configuration may tighten the budget; only widening it is an error."""
    assert resolve_gate_timeout_seconds(_TimeoutEnv("5.5")) == 5.5


@pytest.mark.parametrize("raw", ["30.001", "31", "120", "3600"])
def test_caller_budget_rejects_anything_above_the_ceiling(raw):
    """Rejected, not clamped: min(configured, 30) would be configuration fiction."""
    with pytest.raises(GateIntegrationError) as excinfo:
        resolve_gate_timeout_seconds(_TimeoutEnv(raw))
    assert "30" in str(excinfo.value)
    assert excinfo.value.failure_class == "permanent"


@pytest.mark.parametrize("raw", ["0", "0.0", "-1", "-30"])
def test_caller_budget_rejects_non_positive_values(raw):
    with pytest.raises(GateIntegrationError):
        resolve_gate_timeout_seconds(_TimeoutEnv(raw))


@pytest.mark.parametrize("raw", ["thirty", "30s", "", "  "])
def test_caller_budget_rejects_or_defaults_unparseable_values(raw):
    """Blank falls back to the default; a non-numeric string is a config error."""
    if raw.strip():
        with pytest.raises(GateIntegrationError):
            resolve_gate_timeout_seconds(_TimeoutEnv(raw))
    else:
        assert resolve_gate_timeout_seconds(_TimeoutEnv(raw)) == DEFAULT_GATE_TIMEOUT_SECONDS


@pytest.mark.parametrize("raw", ["inf", "Infinity", "-inf", "nan", "NaN"])
def test_caller_budget_rejects_non_finite_values(raw):
    """float() parses these; `nan > 30` is False, so an explicit isfinite check is required."""
    with pytest.raises(GateIntegrationError):
        resolve_gate_timeout_seconds(_TimeoutEnv(raw))


def test_packet_budget_is_derived_from_the_same_validated_value():
    """The HTTP budget and the advertised packet budget read one config object.

    `send_action` builds the config once and uses `config.timeout_seconds` for
    both `GateClient(config)` and `timeout_ms`; there is no second parse and no
    literal, so the two cannot diverge through the supported builder path.
    """
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "timeout_ms=int(float(config.timeout_seconds) * 1000)" in src
    assert "GateClient(config)" in src
    # No second, unvalidated read of the ICP timeout anywhere in the client.
    assert "plasticos.gate.timeout_seconds" not in src


# ── transport failures must stay diagnosable ──────────────────────────────


def test_empty_transport_failure_message_falls_back_to_the_exception_type():
    """A timeout stringifies to "" — the durable record must not be blank.

    Measured on a real Gate transport: an exhausted caller budget raises httpx
    `ConnectTimeout` with `str(exc) == ""`, so the operator saw
    "Gate enrichment failed (retryable): " and the enrichment run stored
    validation_issues=[""]. Right classification, no reason.
    """
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "detail = str(exc) or type(exc).__name__" in src
    assert "raise GateIntegrationError(detail," in src
    assert "raise GateIntegrationError(str(exc)," not in src


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (TimeoutError(), "TimeoutError"),
        (ConnectionError(), "ConnectionError"),
        (ValueError("a real message"), "a real message"),
    ],
)
def test_failure_detail_is_never_blank(exc, expected):
    """The fallback rule itself: type name when blank, the message otherwise."""
    assert (str(exc) or type(exc).__name__) == expected


def test_the_ceiling_is_a_single_named_constant():
    """One place to change the budget, so config and packet cannot drift apart."""
    src = (ROOT / "plasticos_gate" / "services" / "gate_config.py").read_text(encoding="utf-8")
    assert src.count("MAX_GATE_TIMEOUT_SECONDS = ") == 1
    assert MAX_GATE_TIMEOUT_SECONDS == 30.0


def test_packet_timeout_header_is_derived_from_the_same_config():
    """The header must not advertise the SDK's fixed 30000 while the client waits
    on a different configured budget."""
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "timeout_ms=int(float(config.timeout_seconds) * 1000)" in src


def test_odoo_adds_no_retry_loop_around_gate():
    """EIE owns retries; Odoo fails promptly and persists operator state."""
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "for attempt in range" not in src
    assert "while True" not in src

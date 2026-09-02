"""Drive the REAL IB-Odoo_19 Gate bridge against a REAL Constellation.Gate + EIE.

Four-repo end-to-end: this process runs ``plasticos_gate/services`` exactly as
Odoo does — ``build_converge_request`` -> ``send_converge_action`` ->
``GateClient.execute`` (the installed constellation-node-sdk) -> HTTP -> Gate
``/v1/execute`` -> EIE ``/v1/execute`` -> back -> ``map_converge_response`` ->
partner writeback proposal. Only the Odoo ORM is absent: ``env``, ``run`` and
``partner`` are minimal stand-ins exposing exactly the attributes the bridge
reads. Every socket connect this process makes is recorded so Gate-only egress
is proven by observation, not by assertion.

Not collected by pytest (no ``test_`` prefix): it needs live services. See
README.md in this directory for the launch sequence.

Usage:
    python tests/e2e/four_repo/odoo_driver.py [MODE] [GATE_URL] [TIMEOUT_SECONDS]

    MODE:  happy | invalid_request | unknown_action   (default: happy)
    env:   E2E_RUN_ID (default 7) — the durable run id; a new id is a new
           logical operation, the same id replays Gate's cached answer.
           E2E_ATTEMPT (default 1) — operator retry counter (ADR-006).
           PLASTICOS_GATE_SIGNING_KEY / PLASTICOS_GATE_SIGNING_KEY_ID — sign
           the packet (Gate must hold the same key under that id).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

MODE = sys.argv[1] if len(sys.argv) > 1 else "happy"
GATE_URL = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("FOUR_REPO_GATE_URL", "http://127.0.0.1:9000")
TIMEOUT = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("FOUR_REPO_TIMEOUT_SECONDS", "30")

CONNECTS: list[tuple] = []
_orig_connect = socket.socket.connect


def _recording_connect(self, addr):
    CONNECTS.append(addr if isinstance(addr, tuple) else (str(addr),))
    return _orig_connect(self, addr)


socket.socket.connect = _recording_connect  # type: ignore[method-assign]

from plasticos_gate.services import gate_client as gc  # noqa: E402
from plasticos_gate.services.gate_builders import build_converge_request  # noqa: E402
from plasticos_gate.services.gate_config import (  # noqa: E402
    GateCapability,
    GateIntegrationError,
    classify_gate_availability,
    gate_enrichment_enabled,
)
from plasticos_gate.services.gate_mappers import (  # noqa: E402
    extract_audit_metadata,
    map_converge_response,
    partner_writeback_from_converge,
)


class _Icp:
    def __init__(self, params):
        self._params = params

    def sudo(self):
        return self

    def get_param(self, key, default=None):
        return self._params.get(key, default)


class _Env:
    """What the bridge reads from ``odoo.api.Environment`` — nothing more."""

    def __init__(self, url, timeout):
        self._icp = _Icp(
            {
                "plasticos.gate.url": url,
                "plasticos.gate.allow_insecure_http": "1",
                "plasticos.gate.local_node": "odoo",
                "plasticos.gate.org_id": "plasticos",
                "plasticos.gate.timeout_seconds": timeout,
                "plasticos.gate.enrichment_enabled": "1",
                "plasticos.gate.enrichment_action": "converge" if MODE != "unknown_action" else "no-such-action",
                "plasticos.gate.signing_key_id": os.environ.get("PLASTICOS_GATE_SIGNING_KEY_ID", ""),
                "plasticos.gate.signing_algorithm": "hmac-sha256",
                "plasticos.gate.verify_response_signatures": os.environ.get("PLASTICOS_GATE_VERIFY_RESPONSES", "0"),
            }
        )
        self.cr = type("Cr", (), {"dbname": "plasticos_e2e"})()
        self.user = type("User", (), {"id": 2})()
        self.company = type("Company", (), {"id": 1})()

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        return self._icp


class _Partner:
    _fields = dict.fromkeys(("name", "website", "city", "zip", "street", "street2", "comment", "email", "phone"), 1)

    def __init__(self):
        self.id = 55
        self._vals = {"name": "Acme Recycling", "city": "Charlotte"}

    def __getitem__(self, field):
        return self._vals.get(field, False)


class _Run:
    _name = "plasticos.enrichment.run"
    source_ids = ()

    def __init__(self):
        self.id = int(os.environ.get("E2E_RUN_ID", "7"))
        self.gate_attempt = int(os.environ.get("E2E_ATTEMPT", "1"))
        self.partner_id = _Partner()


def main() -> int:
    env = _Env(GATE_URL, TIMEOUT)
    verdict = classify_gate_availability(env, capability=GateCapability.ENRICHMENT)
    print("availability:", json.dumps(verdict.as_dict()))
    assert gate_enrichment_enabled(env)

    request = build_converge_request(env, _Run())
    payload = request.to_dict()
    if MODE == "invalid_request":
        payload.pop("entity")
    print("odoo->sdk payload:", json.dumps(payload, sort_keys=True))
    print("idempotency_key:", request.idempotency_key)

    started = time.monotonic()
    outcome = 0
    try:
        result = gc.send_converge_action(
            env,
            payload=payload,
            correlation_id=request.odoo.get("correlation_id"),
            idempotency_key=request.idempotency_key,
        )
        elapsed = time.monotonic() - started
        packet = result["packet"]
        print(f"RESULT: transport OK in {elapsed:.2f}s")
        print("response header:", json.dumps(packet.header.model_dump(mode="json"), sort_keys=True))
        print("response address:", packet.address.model_dump())
        print("response hops:", [(h.node, h.direction, h.status) for h in packet.hop_trace])
        print("response payload:", json.dumps(result["payload"], sort_keys=True, default=str)[:1500])
        mapped = map_converge_response(result["payload"])
        audit = extract_audit_metadata(packet)
        print(
            "odoo mapped status:", mapped.status, "| state:", mapped.state, "| failure_reason:", mapped.failure_reason
        )
        print("odoo audit:", audit)
        print("odoo partner writeback proposal:", partner_writeback_from_converge(mapped))
        usable = mapped.status == "ok"
        print("odoo run outcome:", "USABLE (review/injected)" if usable else "DEGRADED (fail closed, no fallback)")
        outcome = 0 if usable else 3
    except GateIntegrationError as exc:
        elapsed = time.monotonic() - started
        print(f"RESULT: GateIntegrationError after {elapsed:.2f}s | failure_class={exc.failure_class} | {exc}")
        cause = exc.__cause__
        print(
            "cause:",
            type(cause).__name__ if cause else None,
            getattr(cause, "status_code", ""),
            (getattr(cause, "response_text", "") or "")[:300],
        )
        outcome = 2
    print("NETWORK CONNECTS (host, port):", sorted({c[:2] for c in CONNECTS}))
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())

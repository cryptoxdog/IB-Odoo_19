"""Real Gate match/converge round-trip integration test (M0 / TASK-046).

Requires a live local five-service stack. Set:
  PLASTICOS_GATE_LIVE_URL=http://127.0.0.1:9000
  PLASTICOS_GATE_ALLOW_INSECURE_HTTP=1

Without those env vars the test is skipped (not marked xfail) so CI stays green
while still providing an executable live proof harness for TASK-046 evidence.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_builders import build_converge_request, build_match_request  # noqa: E402
from plasticos_gate.services.gate_client import send_converge_action, send_match_action  # noqa: E402
from plasticos_gate.services.gate_config import classify_gate_availability  # noqa: E402
from plasticos_gate.services.gate_mappers import map_converge_response, map_match_response  # noqa: E402


def _live_enabled() -> bool:
    return bool((os.environ.get("PLASTICOS_GATE_LIVE_URL") or "").strip())


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="Set PLASTICOS_GATE_LIVE_URL to exercise live Gate match/converge",
)


class _ICP:
    def __init__(self) -> None:
        self._params = {
            "plasticos.gate.url": os.environ["PLASTICOS_GATE_LIVE_URL"].strip(),
            "plasticos.gate.allow_insecure_http": os.environ.get("PLASTICOS_GATE_ALLOW_INSECURE_HTTP", "1"),
            "plasticos.gate.matching_enabled": "1",
            "plasticos.gate.enrichment_enabled": "1",
            "plasticos.gate.local_node": "odoo",
            "plasticos.gate.org_id": "plasticos",
            "plasticos.gate.timeout_seconds": os.environ.get("PLASTICOS_GATE_TIMEOUT", "30"),
        }

    def get_param(self, key: str, default=None):
        return self._params.get(key, default)


class _Env:
    def __init__(self) -> None:
        self.cr = SimpleNamespace(dbname="plasticos_live")
        self.company = SimpleNamespace(id=1)
        self.user = SimpleNamespace(id=1)
        self._icp = _ICP()

    def __getitem__(self, key: str):
        if key == "ir.config_parameter":
            return self
        raise KeyError(key)

    def sudo(self):
        return self

    def get_param(self, key: str, default=None):
        return self._icp.get_param(key, default)


class _FieldProxy:
    def __init__(self, *, code=None, name=None, record_id=None):
        self.code = code
        self.name = name
        self.id = record_id


class _IntakeStub:
    _name = "plasticos.intake"

    def __init__(self) -> None:
        self.id = 42
        self._fields = {
            "polymer_id",
            "form_id",
            "color_id",
            "source_type_id",
            "quantity_per_load_lbs",
            "contamination_pct",
            "mfi_value",
            "lat",
            "lon",
            "partner_id",
        }
        self.polymer_id = _FieldProxy(code="HDPE", name="HDPE", record_id=10)
        self.form_id = _FieldProxy(code="PELLET", name="Pellet", record_id=11)
        self.color_id = _FieldProxy(code="NAT", name="Natural", record_id=12)
        self.source_type_id = _FieldProxy(code="PCR", name="Post Consumer", record_id=13)
        self.quantity_per_load_lbs = 40000.0
        self.contamination_pct = 2.5
        self.mfi_value = 0.8
        self.lat = 35.0
        self.lon = -80.0
        self.partner_id = SimpleNamespace(id=99)

    def __getitem__(self, key):
        return getattr(self, key)


def test_live_gate_availability_is_available():
    env = _Env()
    verdict = classify_gate_availability(env, capability="matching")
    assert verdict.available is True, verdict


def test_live_match_round_trip():
    env = _Env()
    intake = _IntakeStub()
    request = build_match_request(env, intake=intake)
    result = send_match_action(env, payload=request.to_dict(), correlation_id="live-match-m0")
    assert result["payload"] is not None
    mapped = map_match_response(result["payload"])
    assert mapped is not None


def test_live_converge_round_trip():
    env = _Env()

    class _Partner:
        _fields = {"name", "vat", "website", "email", "phone"}

        def __init__(self) -> None:
            self.id = 99
            self.name = "Live Proof Partner"
            self.vat = False
            self.website = False
            self.email = False
            self.phone = False

        def __getitem__(self, key):
            return getattr(self, key)

    run_rec = SimpleNamespace(
        id=7,
        _name="plasticos.enrichment.run",
        partner_id=_Partner(),
        source_ids=False,
    )
    request = build_converge_request(env, run_rec)
    result = send_converge_action(env, payload=request.to_dict(), correlation_id="live-converge-m0")
    assert result["payload"] is not None
    mapped = map_converge_response(result["payload"])
    assert mapped is not None

"""Pure-Python contract tests for plasticos_gate match builders, mappers, and config."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_builders import build_match_request  # noqa: E402
from plasticos_gate.services.gate_config import gate_matching_enabled  # noqa: E402
from plasticos_gate.services.gate_mappers import (  # noqa: E402
    extract_audit_metadata,
    map_match_response,
    map_match_response_to_matcher_dicts,
)


class _MockICP:
    def __init__(self, params: dict[str, str]):
        self._params = params

    def get_param(self, key: str, default=None):
        return self._params.get(key, default)


class _MockEnv:
    def __init__(self, params: dict[str, str] | None = None):
        self.cr = SimpleNamespace(dbname="testdb")
        self.company = SimpleNamespace(id=1)
        self.user = SimpleNamespace(id=2)
        self._params = params or {}
        self._icp = _MockICP(self._params)

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

    def __init__(self):
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


def test_gate_matching_enabled_false_when_url_empty():
    env = _MockEnv({"plasticos.gate.matching_enabled": "1"})
    assert gate_matching_enabled(env) is False


def test_gate_matching_enabled_false_when_flag_off():
    env = _MockEnv(
        {
            "plasticos.gate.url": "https://gate.example.com",
            "plasticos.gate.matching_enabled": "0",
        }
    )
    assert gate_matching_enabled(env) is False


def test_build_match_request_maps_intake_fields():
    env = _MockEnv()
    intake = _IntakeStub()
    request = build_match_request(env, intake=intake, top_n=5, mode="strict")
    assert request.query["polymer_type"] == "HDPE"
    assert request.query["form"] == "PELLET"
    assert request.query["color"] == "NAT"
    assert request.query["quantity_per_load_lbs"] == 40000.0
    assert request.query["contamination_pct"] == 2.5
    assert request.query["intake_id"] == 42
    assert request.query["supplier_partner_id"] == 99
    assert request.query["mode"] == "strict"
    assert request.top_n == 5
    assert request.odoo["model"] == "plasticos.intake"
    assert request.odoo["record_id"] == 42


def test_map_match_response_to_matcher_dicts():
    payload = {
        "status": "ok",
        "results": [
            {
                "buyer_partner_id": 7,
                "buyer_name": "Buyer Co",
                "score": 85,
                "facility_profile_id": 3,
                "reason": "Strong fit",
                "typical_price": 0.42,
                "gates_passed": 8,
                "gates_failed": ["gate_3"],
            }
        ],
    }
    mapped = map_match_response(payload)
    rows = map_match_response_to_matcher_dicts(
        mapped,
        audit_metadata={"gate_packet_id": "pkt-1", "gate_correlation_id": "corr-1"},
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["buyer_id"] == 7
    assert row["buyer_name"] == "Buyer Co"
    assert row["total_score"] == pytest.approx(0.85)
    assert row["match_source"] == "gate"
    assert row["gate_packet_id"] == "pkt-1"
    assert row["gate_correlation_id"] == "corr-1"
    assert row["gates_failed"] == ["gate_3"]


def test_extract_audit_metadata_reads_packet_header():
    packet = MagicMock()
    packet.header.packet_id = "abc-123"
    packet.header.correlation_id = "corr-xyz"
    audit = extract_audit_metadata(packet)
    assert audit["gate_packet_id"] == "abc-123"
    assert audit["gate_correlation_id"] == "corr-xyz"

"""TASK-032 contract: Gate-only intelligence invariant under dual-write."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs/adr/ADR-125-odoo-dual-write-controls.md"
RUNBOOK = ROOT / "docs/runbooks/ODOO_DUAL_WRITE.md"
SEED = ROOT / "plasticos_gate/data/gate_icp_seed.xml"
SVC = ROOT / "plasticos_gate/services/dual_write.py"
AUTH = ROOT / "tests/contracts/test_external_intelligence_authority.py"


def test_adr_and_runbook_exist() -> None:
    assert ADR.is_file()
    text = ADR.read_text()
    assert "dual_write_enabled" in text
    assert "local" in text.lower() and "authority" in text.lower()
    assert "opt-in" in text.lower() or "defaults to" in text.lower()
    assert RUNBOOK.is_file()
    rb = RUNBOOK.read_text()
    assert "plasticos.gate.dual_write_enabled" in rb
    assert "Disable" in rb or "disable" in rb


def test_icp_seed_opt_in_default_off() -> None:
    xml = SEED.read_text()
    assert "plasticos.gate.dual_write_enabled" in xml
    # default value 0 appears for the dual_write record
    assert "param_gate_dual_write_enabled" in xml


def test_service_forbids_local_intelligence_authority() -> None:
    src = SVC.read_text()
    assert "local_intelligence_authority=False" in src or "local_intelligence_authority: bool = False" in src
    assert "buyer.matcher" not in src.lower() or "forbidden" in src.lower()
    assert "Gate" in src or "gate_authority" in src


def test_external_authority_contract_still_present() -> None:
    assert AUTH.is_file()
    text = AUTH.read_text()
    assert "Single External Intelligence Authority" in text or "external_intelligence" in text

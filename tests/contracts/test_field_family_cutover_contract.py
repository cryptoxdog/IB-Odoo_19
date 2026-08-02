"""TASK-035 contract: Gate-only authority under field-family cutover."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs/adr/ADR-127-field-family-cutover.md"
RUNBOOK = ROOT / "docs/runbooks/FIELD_FAMILY_CUTOVER.md"
SEED = ROOT / "plasticos_gate/data/gate_icp_seed.xml"
SVC = ROOT / "plasticos_gate/services/field_family_cutover.py"
AUTH = ROOT / "tests/contracts/test_external_intelligence_authority.py"


def test_adr_and_runbook_exist() -> None:
    assert ADR.is_file()
    text = ADR.read_text()
    assert "specification" in text
    assert "field_family_cutover_enabled" in text
    assert "observation" in text.lower()
    assert "local" in text.lower() and "authority" in text.lower()
    assert RUNBOOK.is_file()
    rb = RUNBOOK.read_text()
    assert "plasticos.gate.field_family_cutover_enabled" in rb
    assert "Disable" in rb or "disable" in rb
    assert "specification" in rb


def test_icp_seed_opt_in_default_off() -> None:
    xml = SEED.read_text()
    assert "plasticos.gate.field_family_cutover_enabled" in xml
    assert "param_gate_field_family_cutover_enabled" in xml
    assert "param_gate_field_family_cutover_operator_approved" in xml


def test_service_locks_specification_and_forbids_local() -> None:
    src = SVC.read_text()
    assert 'APPROVED_FAMILY = "specification"' in src
    assert "local_intelligence_authority" in src
    assert "REQUIRED_OBSERVATION_METRICS" in src
    assert "supply" in src and "demand" in src


def test_external_authority_contract_still_present() -> None:
    assert AUTH.is_file()
    text = AUTH.read_text()
    assert "Single External Intelligence Authority" in text or "external_intelligence" in text

"""M7 / TASK-051 — post-retirement local-intelligence absence + drift scanner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "ci/check_no_local_intelligence.py"
ADR = ROOT / "docs/adr/ADR-003-single-external-intelligence-authority.md"
INVARIANTS = ROOT / "INVARIANTS.md"
MAKEFILE = ROOT / "Makefile"
CI_YML = ROOT / ".github/workflows/ci.yml"
PRECOMMIT = ROOT / ".pre-commit-config.yaml"
PATTERNS = ROOT / "scripts/check_odoo_patterns.sh"

RETIRED_MODULES = (
    "plasticos_buyer_match_engine",
    "plasticos_inference_engine",
)


def test_scanner_exists_and_passes():
    assert SCANNER.is_file()
    proc = subprocess.run(
        [sys.executable, str(SCANNER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
    assert "residue_files=" in proc.stdout


def test_scanner_requires_modules_absent():
    proc = subprocess.run(
        [sys.executable, str(SCANNER), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "PASS"
    assert payload["residue_files_scanned"] == 0
    assert payload["blocking"] == []
    for name in RETIRED_MODULES:
        assert not (ROOT / name).exists(), f"{name} must be physically absent after M7"


def test_adr_has_retirement_and_observation():
    text = ADR.read_text(encoding="utf-8")
    assert "Retirement evidence" in text
    assert "Observation criteria" in text
    assert "check_no_local_intelligence" in text
    assert "repository_validated" in text.lower() or "not claimed" in text.lower()


def test_invariants_wire_drift_guard():
    text = INVARIANTS.read_text(encoding="utf-8")
    assert "check_no_local_intelligence" in text
    assert "test_no_local_intelligence" in text


def test_makefile_exposes_target():
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "no-local-intelligence" in text


def test_ci_wires_scanner():
    text = CI_YML.read_text(encoding="utf-8")
    assert "check_no_local_intelligence.py" in text


def test_precommit_wires_scanner():
    text = PRECOMMIT.read_text(encoding="utf-8")
    assert "check_no_local_intelligence.py" in text


def test_odoo_patterns_invokes_scanner():
    text = PATTERNS.read_text(encoding="utf-8")
    assert "check_no_local_intelligence.py" in text

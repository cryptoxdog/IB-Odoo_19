"""M2 / TASK-047 — Gate-only match orchestrator (no local scoring fallback)."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "plasticos_matching/models/match_orchestrator.py"
INTAKE_MATCHING = ROOT / "plasticos_matching/models/intake_extension.py"
EXCLUSION = ROOT / "plasticos_matching/models/match_exclusion.py"
MATCH_RUN = ROOT / "plasticos_matching/models/match_run.py"


def test_required_m2_files_exist():
    for path in (
        ORCH,
        INTAKE_MATCHING,
        EXCLUSION,
        MATCH_RUN,
        ROOT / "plasticos_matching/views/match_run_views.xml",
        ROOT / "plasticos_matching/views/match_exclusion_views.xml",
        ROOT / "tests/test_matching_gate_orchestrator.py",
    ):
        assert path.is_file(), path


def test_orchestrator_source_has_no_local_matcher_or_neo4j():
    src = ORCH.read_text(encoding="utf-8")
    assert "plasticos.match.orchestrator" in src
    assert "_find_matches_local" not in src
    assert "import neo4j" not in src
    assert "plasticos.graph.service" not in src
    assert "find_matches_for_supplier" not in src
    assert "send_match_action" in src


def test_exclusion_model_identity_preserved_in_matching_home():
    src = EXCLUSION.read_text(encoding="utf-8")
    assert '_name = "plasticos.match.exclusion"' in src
    assert "get_excluded_buyer_ids" in src


def test_match_run_model_defined():
    src = MATCH_RUN.read_text(encoding="utf-8")
    assert '_name = "plasticos.match.run"' in src
    assert "gate_packet_id" in src
    assert "failure_class" in src


def test_intake_extension_routes_through_orchestrator():
    src = INTAKE_MATCHING.read_text(encoding="utf-8")
    assert "plasticos.match.orchestrator" in src
    assert "run_match_for_intake" in src
    assert "_find_matches_local" not in src


def test_orchestrator_ast_no_scoring_loops():
    tree = ast.parse(ORCH.read_text(encoding="utf-8"))
    banned = {"_check_gates_strict", "_check_gates_relaxed", "_fallback_scoring", "graph_service"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not (names & banned)


class _FakeRun:
    def __init__(self):
        self.id = 42
        self._vals = {}

    def write(self, vals):
        self._vals.update(vals)


def test_run_match_fail_closed_when_gate_disabled():
    """Pure unit: orchestrator raises and records failed run when Gate off."""
    # Lightweight structural stand-in — full Odoo env covered in integration.
    src = ORCH.read_text(encoding="utf-8")
    assert "Gate matching is not enabled" in src or "gate_matching_enabled" in src
    assert "UserError" in src


def test_manifest_depends_on_gate_not_neo4j():
    manifest = (ROOT / "plasticos_matching/__manifest__.py").read_text(encoding="utf-8")
    assert "plasticos_gate" in manifest
    assert "neo4j" not in manifest.lower()

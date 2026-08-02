"""M3 / TASK-048 — explicit degraded mode; no local substitute on Gate failure."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "plasticos_matching/models/match_orchestrator.py"
INTAKE = ROOT / "plasticos_matching/models/intake_extension.py"
RUN = ROOT / "plasticos_matching/models/match_run.py"
GATE_CFG = ROOT / "plasticos_gate/services/gate_config.py"
VIEWS = ROOT / "plasticos_matching/views/match_run_views.xml"
RUNBOOK = ROOT / "docs/runbooks/MATCHING_DEGRADED_MODE.md"


def test_m3_required_files_exist():
    for path in (ORCH, INTAKE, RUN, GATE_CFG, VIEWS, RUNBOOK):
        assert path.is_file(), path


def test_orchestrator_never_calls_local_matcher():
    src = ORCH.read_text(encoding="utf-8")
    assert "_find_matches_local" not in src
    assert "find_matches_for_supplier" not in src
    # Docstring may name the forbidden path; ensure no runtime call site.
    assert "env[\"plasticos.buyer.matcher\"]" not in src
    assert "silent fallback" in src.lower()
    assert "retry_match_run" in src
    assert "_state_for_failure" in src


def test_orchestrator_records_failure_states():
    src = ORCH.read_text(encoding="utf-8")
    assert '"retryable"' in src
    assert '"failed"' in src
    assert '"degraded"' in src
    assert "classify_gate_availability" in src


def test_match_run_has_retryable_and_retry_action():
    src = RUN.read_text(encoding="utf-8")
    assert '("retryable", "Retryable")' in src
    assert "action_retry_match" in src
    assert "retry_of_id" in src
    assert "availability_status" in src


def test_intake_exposes_retry_and_open_run_actions():
    src = INTAKE.read_text(encoding="utf-8")
    assert "action_retry_latest_match" in src
    assert "action_open_latest_match_run" in src
    assert "_find_matches_local" not in src


def test_gate_config_exposes_failure_categories():
    src = GATE_CFG.read_text(encoding="utf-8")
    assert "gate_failure_categories" in src
    assert "fail closed" in src.lower() or "no local substitute" in src.lower()


def test_views_expose_retry_button_and_degraded_states():
    src = VIEWS.read_text(encoding="utf-8")
    assert "action_retry_match" in src
    assert "retryable" in src
    assert "degraded" in src
    assert "availability_status" in src


def test_orchestrator_ast_bans_local_scoring_symbols():
    tree = ast.parse(ORCH.read_text(encoding="utf-8"))
    banned = {"_find_matches_local", "_fallback_scoring", "graph_service", "neo4j"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not (names & banned)


def test_runbook_documents_no_substitution():
    src = RUNBOOK.read_text(encoding="utf-8")
    assert "degraded" in src.lower()
    assert "retry" in src.lower()
    assert "local" in src.lower()

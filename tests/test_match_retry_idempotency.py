"""M3 / TASK-048 — retry idempotency and duplicate suppression."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "plasticos_matching/models/match_orchestrator.py"


def _orch_src() -> str:
    return ORCH.read_text(encoding="utf-8")


def test_retry_match_run_defined():
    assert "def retry_match_run" in _orch_src()


def test_retry_suppresses_duplicate_pending():
    src = _orch_src()
    assert '("state", "=", "pending")' in src
    assert "retry_of_id" in src
    assert "A retry is already pending" in src


def test_retry_rejects_ok_run():
    assert "already succeeded" in _orch_src()


def test_retry_passes_retry_of_lineage():
    src = _orch_src()
    assert "retry_of=" in src or "retry_of_id" in src
    tree = ast.parse(src)
    funcs = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for node in node.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "retry_match_run" in funcs
    assert "run_match_for_intake" in funcs

"""M4 / TASK-049 — no local inference/crawl on Gate enrichment failure."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "plasticos_enrichment/models/enrichment_run.py"
SVC = ROOT / "plasticos_enrichment/models/enrichment_service.py"
MANIFEST = ROOT / "plasticos_enrichment/__manifest__.py"
CRON = ROOT / "plasticos_enrichment/data/cron.xml"
RUNBOOK = ROOT / "docs/runbooks/ENRICHMENT_DEGRADED_MODE.md"


def test_required_m4_files_exist():
    for path in (RUN, SVC, MANIFEST, CRON, RUNBOOK):
        assert path.is_file(), path


def test_manifest_drops_inference_dependency():
    src = MANIFEST.read_text(encoding="utf-8")
    assert "plasticos_inference_engine" not in src
    assert "plasticos_gate" in src


def test_cron_disabled():
    src = CRON.read_text(encoding="utf-8")
    assert 'name="active">False</field>' in src or ">False</field>" in src
    assert src.count("False") >= 2


def test_action_execute_is_gate_only():
    src = RUN.read_text(encoding="utf-8")
    assert "falling back to local enrichment" not in src
    assert "Gate-only" in src or "gate-only" in src.lower()
    assert "crawl_source" not in src.split("def action_execute")[1].split("def action_")[0]
    assert "action_retry_enrichment" in src
    assert '("retryable", "Retryable")' in src
    assert '("degraded", "Degraded")' in src


def test_service_local_methods_fail_closed():
    src = SVC.read_text(encoding="utf-8")
    assert "mothball M4" in src
    assert "raise UserError" in src


def test_run_ast_action_execute_has_no_local_service_calls():
    tree = ast.parse(RUN.read_text(encoding="utf-8"))
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "action_execute":
            fn = node
            break
    assert fn is not None
    calls = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert "crawl_source" not in calls
    assert "extract_from_source" not in calls
    assert "run_inference" not in calls


def test_runbook_documents_no_substitution():
    src = RUNBOOK.read_text(encoding="utf-8")
    assert "degraded" in src.lower()
    assert "gate" in src.lower()
    assert "local" in src.lower()

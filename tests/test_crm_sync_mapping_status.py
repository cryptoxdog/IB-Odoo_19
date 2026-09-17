"""VanillaSoft mapping-status contract: the documented mapping must match the code.

Pure-python tier (no Odoo import) — AST contract style, like
tests/test_legacy_erp_import_contract.py. The runbook table
(docs/runbooks/CRM_SYNC_VANILLASOFT.md, "Field mapping status") is the
human-facing status SSOT; this test pins the code to it.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RUNBOOK = ROOT / "docs" / "runbooks" / "CRM_SYNC_VANILLASOFT.md"
ORCHESTRATOR = ROOT / "plasticos_crm_sync" / "services" / "orchestrator.py"
SUMMARY = ROOT / "plasticos_crm_sync" / "services" / "import_summary.py"


def _ast_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {module}")


def _return_keys(func: ast.FunctionDef) -> set[str]:
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            keys: set[str] = set()
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
            return keys
    raise AssertionError(f"{func.name} has no literal dict return")


def test_every_lead_vals_key_is_documented():
    """Every `_lead_vals_from_dto` return key must appear in the runbook mapping."""
    module = _ast_module(ORCHESTRATOR)
    keys = _return_keys(_function(module, "_lead_vals_from_dto"))
    runbook = RUNBOOK.read_text(encoding="utf-8")
    missing = [key for key in sorted(keys) if key not in runbook]
    assert not missing, f"_lead_vals_from_dto keys undocumented in {RUNBOOK.name}: {missing}"


def test_upsert_classification_vocabulary_is_pinned():
    """The deterministic classification contract must stay in _upsert_lead."""
    module = _ast_module(ORCHESTRATOR)
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    source = ast.get_source_segment(text, _function(module, "_upsert_lead")) or ""
    for marker in ("created", "updated", "unchanged", "duplicate_rejected", "failed"):
        assert marker in source, f"_upsert_lead no longer classifies {marker!r}"


def test_unchanged_records_are_not_written():
    """Unchanged leads must take the no-write path (outcome, not write())."""
    module = _ast_module(ORCHESTRATOR)
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    source = ast.get_source_segment(text, _function(module, "_upsert_lead")) or ""
    assert 'outcome = "unchanged"' in source
    assert "lead.write(changed)" in source


def test_runbook_declares_the_status_vocabulary():
    runbook = RUNBOOK.read_text(encoding="utf-8")
    for status in ("VERIFIED", "NEEDS_CORRECTION", "UNMAPPED_INTENTIONALLY", "UNKNOWN"):
        assert status in runbook


def test_summary_projection_uses_the_shared_schema():
    """The VS summary must feed the same import-run-summary contract."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_vs_summary", SUMMARY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class _Run:
        contacts_seen = 10
        calls_seen = 5
        contacts_created = 8
        contacts_updated = 1
        contacts_unchanged = 1
        contacts_duplicate_rejected = 0
        contacts_failed = 0
        calls_created = 4
        calls_updated = 1
        calls_unchanged = 0
        calls_failed = 0
        status = "success"

    from scripts.validate_import_summary import validate_summary

    summary = module.build_run_summary(_Run())
    assert validate_summary(summary) == []
    assert summary["records_seen"] == 15
    assert summary["records_created"] == 12
    assert summary["records_updated"] == 2
    assert summary["final_status"] == "success"

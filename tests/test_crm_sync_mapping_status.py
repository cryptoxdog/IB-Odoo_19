"""VanillaSoft mapping-status contract: code classification stays explicit.

Pure-python tier (no Odoo import) — AST contract style, like
tests/test_erp_import_contract.py. The upsert vocabulary and the no-write
path are pinned on the orchestrator, not on a separate prose document.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ORCHESTRATOR = ROOT / "plasticos_crm_sync" / "services" / "orchestrator.py"
SUMMARY = ROOT / "plasticos_crm_sync" / "services" / "import_summary.py"


def _ast_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {module}")


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


def test_projected_errors_keep_typed_evidence_and_reject_extra_keys():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_vs_summary_project", SUMMARY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from scripts.validate_import_summary import validate_summary

    class _Run:
        contacts_seen = 1
        calls_seen = 0
        contacts_created = 1
        contacts_updated = 0
        contacts_unchanged = 0
        contacts_duplicate_rejected = 0
        contacts_failed = 0
        calls_created = 0
        calls_updated = 0
        calls_unchanged = 0
        calls_failed = 0
        status = "success"

    summary = module.build_run_summary(
        _Run(),
        error_rows=[
            {
                "record_ref": "vs-1",
                "message": "missing polymer",
                "category": "required_mapping",
                "error_type": "ValidationError",
                "informational": False,
                "secret_note": "drop me",
            }
        ],
    )
    assert validate_summary(summary) == []
    assert summary["final_status"] == "partial"
    assert summary["errors"] == [
        {
            "record_ref": "vs-1",
            "message": "missing polymer",
            "category": "required_mapping",
            "error_type": "ValidationError",
        }
    ]
    assert module.business_acceptance(summary) == "FAIL"
    assert (
        module.business_acceptance(
            {
                "final_status": "success",
                "errors": [{"record_ref": "vs-1", "message": "missing polymer", "category": "required_mapping"}],
            }
        )
        == "FAIL"
    )
    leaked = dict(summary)
    leaked["errors"] = [{"record_ref": "vs-1", "message": "missing polymer", "unexpected": True}]
    assert any("unexpected field" in error for error in validate_summary(leaked))
    long_message = "x" * 2500
    capped = module.project_error_rows([{"record_ref": "vs-long", "message": long_message}])
    assert len(capped[0]["message"]) == 2000
    assert (
        validate_summary(
            module.build_run_summary(
                _Run(), error_rows=[{"record_ref": "vs-long", "message": long_message, "category": "required_mapping"}]
            )
        )
        == []
    )
    overflow = [
        {"record_ref": str(index), "message": "optional", "category": "optional_context"} for index in range(1000)
    ]
    overflow.append({"record_ref": "kept", "message": "required mapping", "category": "required_mapping"})
    projected = module.project_error_rows(overflow)
    assert len(projected) == 1000
    assert projected[0]["record_ref"] == "kept"
    import json

    unsafe = module.project_error_rows(
        [{"record_ref": "vs-secret", "message": "password=hunter2", "category": "required_mapping"}]
    )
    assert "hunter2" not in unsafe[0]["message"]
    assert "[redacted]=" not in unsafe[0]["message"]
    assert unsafe[0]["record_ref"] == "vs-secret"
    assert unsafe[0]["category"] == "required_mapping"
    harmless = "HTTP 504 timeout for contact vs-42 category required_mapping"
    fixtures = [
        "password=hunter2",
        "PaSsWoRd=Hunter2",
        'api_key: "ab cd"',
        "token=one, token=two",
        "password=hunter2; timeout=30",
        "Authorization: Bearer eyJraw.secret",
        "Authorization: APIKey=synthetic-key",
        '"password": "json-secret"',
        f"password=hunter2 {harmless} " + ("x" * 2500),
    ]
    secret_values = (
        "hunter2",
        "Hunter2",
        "ab cd",
        "one",
        "two",
        "eyJraw.secret",
        "synthetic-key",
        "json-secret",
    )
    for fixture in fixtures:
        projected = module.project_error_rows(
            [{"record_ref": "vs-42", "message": fixture, "category": "required_mapping"}]
        )
        message = projected[0]["message"]
        for secret in secret_values:
            assert secret not in message
        assert "password=" not in message.casefold()
        assert "token=" not in message.casefold()
        assert "[redacted]=" not in message
    readable = module._public_message(harmless)
    assert readable == harmless
    capped = module._public_message(f"password=hunter2 {harmless} " + ("x" * 2500))
    assert "hunter2" not in capped
    assert "HTTP 504" in capped
    assert "vs-42" in capped
    assert len(capped) == 2000
    secret_summary = module.build_run_summary(
        _Run(),
        error_rows=[
            {
                "record_ref": "vs-secret",
                "message": "AuthenticationError: password=hunter2 api_key=synthetic-key authorization: Bearer eyJraw.secret",
                "category": "required_mapping",
                "error_type": "AuthenticationError",
            }
        ],
    )
    serialized = json.dumps(secret_summary)
    for secret in ("hunter2", "synthetic-key", "eyJraw.secret"):
        assert secret not in serialized
    assert secret_summary["errors"][0]["record_ref"] == "vs-secret"
    assert secret_summary["errors"][0]["category"] == "required_mapping"
    assert secret_summary["errors"][0]["error_type"] == "AuthenticationError"
    assert secret_summary["final_status"] == "partial"
    assert module.business_acceptance(secret_summary) == "FAIL"
    assert validate_summary(secret_summary) == []
    assert (
        validate_summary(
            module.build_run_summary(
                _Run(),
                error_rows=[{"record_ref": "vs-secret", "message": "password=hunter2", "category": "required_mapping"}],
            )
        )
        == []
    )

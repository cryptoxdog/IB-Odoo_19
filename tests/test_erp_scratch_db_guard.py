"""The ERP runtime gate may drop a database. Prove a refused identity never reaches that SQL.

The live gate imports Odoo, so this module executes the scratch lifecycle
directly. A connector that records a call fails the test: refusal must happen
before a connection exists, and therefore before DROP or CREATE.
"""

from __future__ import annotations

import ast
import builtins
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tests" / "runtime_gates" / "run_erp_import.py"
LIFECYCLE = ROOT / "tests" / "runtime_gates" / "scratch_db.py"


def _load_lifecycle():
    spec = importlib.util.spec_from_file_location("erp_scratch_db", LIFECYCLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scratch_db = _load_lifecycle()


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined")


def _call_lines(tree: ast.AST, attr_or_name: str) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == attr_or_name:
            lines.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == attr_or_name:
            lines.append(node.lineno)
    return lines


class _SqlImportForbidden:
    """Fail if a refused identity reaches the adapter that builds DROP/CREATE."""

    def __enter__(self):
        real = builtins.__import__

        def guarded(name, global_ns=None, local_ns=None, fromlist=(), level=0):
            if name == "psycopg2" or name.startswith("psycopg2."):
                raise AssertionError("psycopg2 imported on a refused database identity")
            return real(name, global_ns, local_ns, fromlist, level)

        self._patch = patch("builtins.__import__", guarded)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        return False


# scratch, template, stage, message fragment. Each name is refused for the
# reason in the fragment, and both lifecycle operations are covered below.
_REFUSALS = [
    ("erp_import_gate; DROP DATABASE postgres", "plasticos_template", "", "not a safe database identifier"),
    ("", "plasticos_template", "", "not a safe database identifier"),
    ("has space", "plasticos_template", "", "not a safe database identifier"),
    ("erp_import_gate", "template; DROP DATABASE postgres", "", "L9_ODOO_TEMPLATE_DB"),
    ("erp_import_gate", "erp_import_gate", "", "it is the template database"),
    ("plasticos_template", "plasticos_template", "", "it is the template database"),
    ("ERP_IMPORT_GATE", "erp_import_gate", "", "it is the template database"),
    ("erp_import_gate_production", "plasticos_template", "", "identifies as production"),
    ("erp_import_gate_prod", "plasticos_template", "", "identifies as production"),
    ("production", "plasticos_template", "", "identifies as production"),
    ("erp_import_gate", "plasticos_template", "production", "ODOO_STAGE=production"),
    ("erp_import_gate", "plasticos_template", " Production ", "ODOO_STAGE=production"),
    ("postgres", "plasticos_template", "", "system database"),
    ("template0", "plasticos_template", "", "system database"),
    ("template1", "plasticos_template", "", "system database"),
    ("odoo", "plasticos_template", "", "only an erp_import_gate database is disposable"),
    ("plasticos", "plasticos_template", "", "only an erp_import_gate database is disposable"),
    ("customer_live", "plasticos_template", "", "only an erp_import_gate database is disposable"),
]


@pytest.mark.parametrize("operation", ["create", "drop"])
@pytest.mark.parametrize(("scratch", "template", "stage", "fragment"), _REFUSALS)
def test_refused_identity_never_reaches_destructive_sql(operation, scratch, template, stage, fragment):
    calls: list[str] = []

    def connect(dbname: str):
        calls.append(dbname)
        raise AssertionError(f"opened a connection to {dbname}")

    fn = scratch_db.create_scratch_database if operation == "create" else scratch_db.drop_scratch_database
    with _SqlImportForbidden(), pytest.raises(SystemExit, match=fragment):
        fn(connect, scratch, template, stage=stage)
    assert calls == []


def test_default_scratch_namespace_is_disposable():
    scratch, template = scratch_db.require_disposable_scratch("erp_import_gate", "plasticos_template", stage="")
    assert (scratch, template) == ("erp_import_gate", "plasticos_template")
    scratch, template = scratch_db.require_disposable_scratch("erp_import_gate_g5", "plasticos_template", stage="dev")
    assert (scratch, template) == ("erp_import_gate_g5", "plasticos_template")


def test_guard_runs_before_connection_and_sql_in_both_operations():
    """Source order: identity, then the adapter, then any cursor.execute."""
    tree = ast.parse(LIFECYCLE.read_text(encoding="utf-8"))
    opened = _function(tree, "_open_maintenance")
    guard = _call_lines(opened, "require_disposable_scratch")
    connect = _call_lines(opened, "connect")
    imports = [
        node.lineno
        for node in ast.walk(opened)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("psycopg2")
    ]
    assert guard and connect and imports
    assert min(guard) < min(imports) < min(connect)

    for name in ("create_scratch_database", "drop_scratch_database"):
        func = _function(tree, name)
        open_lines = _call_lines(func, "_open_maintenance")
        execute_lines = _call_lines(func, "execute")
        assert open_lines and execute_lines
        assert min(open_lines) < min(execute_lines)
        constants = [
            node.value
            for node in ast.walk(func)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "DATABASE" in node.value
        ]
        assert constants, f"{name} no longer issues database SQL"


def test_gate_entrypoints_do_not_issue_sql_themselves():
    """DROP/CREATE stay in the guarded lifecycle. The gate file only delegates."""
    source = GATE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name, callee in (
        ("create_scratch_db", "create_scratch_database"),
        ("drop_scratch_db", "drop_scratch_database"),
    ):
        func = _function(tree, name)
        assert _call_lines(func, callee), f"{name} does not call {callee}"
        sql_text = " ".join(
            node.value for node in ast.walk(func) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
        assert "DROP" not in sql_text
        assert "CREATE" not in sql_text

    g5 = _function(tree, "gate_g5_direct_sql_import_reconciles")
    segment = ast.get_source_segment(source, g5) or ""
    assert "PRODUCTION_MARKERS" not in segment
    assert "it identifies as production" not in segment

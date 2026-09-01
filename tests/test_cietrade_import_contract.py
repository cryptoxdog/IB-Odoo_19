"""Structural contract tests for the CieTrade import service.

The service itself needs an Odoo runtime, which the ``pure-python-tests`` CI
tier does not have. These tests assert the properties that must hold *by
construction* and that a runtime test would only catch after a 20k-record run:
per-``BuySellNo`` atomicity, identity-marker ordering, upsert-only writes, and
the absence of any dependency on the retired CSV architecture.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_transaction"))

SERVICE = ROOT / "plasticos_transaction" / "models" / "cietrade_import_service.py"
RUNNER = ROOT / "plasticos_transaction" / "scripts" / "run_cietrade_import.py"
CIETRADE_PKG = ROOT / "plasticos_transaction" / "cietrade"


@pytest.fixture(scope="module")
def service_source() -> str:
    return SERVICE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def service_tree(service_source: str) -> ast.Module:
    return ast.parse(service_source)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined in the import service")


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------
def test_service_is_wired_into_the_module(service_source):
    init = (ROOT / "plasticos_transaction" / "models" / "__init__.py").read_text(encoding="utf-8")
    assert "from . import cietrade_import_service" in init
    assert '_name = "plasticos.cietrade.import"' in service_source


def test_service_declares_an_abstract_model(service_source):
    # An AbstractModel needs no ACL row and creates no table.
    assert "models.AbstractModel" in service_source


def test_runner_entrypoint_exists_and_is_non_interactive():
    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "run" for n in tree.body)
    # No prompt, no UI action — the words may appear in prose, the calls may not.
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "input" not in called
    assert "ir.actions.act_window" not in source.replace("no UI", "")


# ---------------------------------------------------------------------------
# Architecture prohibitions
# ---------------------------------------------------------------------------
def test_import_does_not_depend_on_the_retired_csv_architecture(service_source):
    for forbidden in (
        "plasticos.transaction.import.service",  # retired CSV service
        "ERP.WksDetail.csv",
        "run_csv_import",
        "import csv",
        "TransientModel",  # no wizard
        "ir.cron",
    ):
        assert forbidden not in service_source, f"{forbidden} must not appear in the pipeline"


def test_source_layer_imports_no_odoo_symbol():
    """The source layer must stay runnable in the pure-Python CI tier."""
    for path in sorted(CIETRADE_PKG.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not a.name.startswith("odoo") for a in node.names), path.name
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("odoo"), path.name


def test_source_layer_is_not_imported_at_addon_load_time(service_source):
    """Odoo-free helpers load lazily, inside functions (cross-addon import fence)."""
    tree = ast.parse(service_source)
    for node in tree.body:  # module level only
        assert not isinstance(node, ast.ImportFrom) or "cietrade" not in (node.module or "")


def test_identity_is_never_a_name_email_or_database_id(service_source):
    tree = ast.parse(service_source)
    upsert_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_upsert"
    ]
    assert upsert_calls, "no deterministic upsert calls found"
    for call in upsert_calls:
        xml_id = call.args[1]
        # Every identity is a literal or an f-string over a source key.
        assert isinstance(xml_id, (ast.Constant, ast.JoinedStr))
        rendered = ast.dump(xml_id)
        assert "cietrade_" in rendered


# ---------------------------------------------------------------------------
# Atomicity (gap G09)
# ---------------------------------------------------------------------------
def test_each_buysellno_is_wrapped_in_a_savepoint(service_tree):
    loop = _function(service_tree, "_import_transactions")
    savepoints = [
        node
        for node in ast.walk(loop)
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Attribute)
            and item.context_expr.func.attr == "savepoint"
            for item in node.items
        )
    ]
    assert len(savepoints) == 1, "one savepoint per BuySellNo logical unit"

    # The whole unit — header, lines, identity markers — lives inside it.
    called = {
        node.func.attr
        for node in ast.walk(savepoints[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_import_one_transaction" in called


def test_commit_never_happens_inside_a_transaction_unit(service_tree):
    loop = _function(service_tree, "_import_transactions")
    commits = [
        node
        for node in ast.walk(loop)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "commit"
    ]
    assert len(commits) == 1, "exactly one commit site, between complete transactions"

    inside_savepoint = [
        node
        for with_node in ast.walk(loop)
        if isinstance(with_node, ast.With)
        for node in ast.walk(with_node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "commit"
    ]
    assert not inside_savepoint, "a commit inside the savepoint would break atomicity"


def test_identity_marker_is_created_with_the_record_not_before(service_tree):
    """A marker written ahead of the record would survive a rollback as a lie."""
    upsert = _function(service_tree, "_upsert")
    creates = [
        node
        for node in ast.walk(upsert)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "create"
    ]
    assert len(creates) == 2, "the record and its identity marker"

    record_create, marker_create = sorted(creates, key=lambda n: n.lineno)
    # The record is created first; the ir.model.data marker follows it.
    assert isinstance(record_create.func.value, ast.Name)
    assert record_create.func.value.id == "model"
    assert "ir.model.data" in ast.dump(marker_create.func.value)
    assert record_create.lineno < marker_create.lineno


def test_failed_transaction_is_recorded_and_the_run_continues(service_tree):
    loop = _function(service_tree, "_import_transactions")
    handlers = [node for node in ast.walk(loop) if isinstance(node, ast.ExceptHandler)]
    assert handlers, "a failing BuySellNo must be recorded, not abort the run"
    handler_body = ast.dump(handlers[0])
    assert "error" in handler_body
    assert "Continue" in handler_body or "continue" in handler_body.lower()


# ---------------------------------------------------------------------------
# Idempotency (gap G10)
# ---------------------------------------------------------------------------
def test_every_persisted_entity_goes_through_the_deterministic_upsert(service_tree):
    """No mapper may call ``create`` directly and bypass identity resolution."""
    upsert = _function(service_tree, "_upsert")
    for node in ast.walk(service_tree):
        if not isinstance(node, ast.FunctionDef) or node is upsert:
            continue
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "create":
                raise AssertionError(f"{node.name} calls create() outside _upsert")


def test_upsert_writes_only_what_actually_changed(service_tree):
    """A second run must report ``skipped``, not churn every record."""
    upsert = ast.dump(_function(service_tree, "_upsert"))
    assert "_differs" in upsert
    assert "skipped" in upsert


def test_contact_role_tags_are_applied_as_a_set(service_tree):
    """Tag membership is set semantics, so replaying CRA_ID adds no duplicate."""
    apply_roles = ast.dump(_function(service_tree, "_apply_contact_roles"))
    assert "existing" in apply_roles and "missing" in apply_roles


# ---------------------------------------------------------------------------
# Existing-field policy
# ---------------------------------------------------------------------------
def test_no_new_field_is_declared_by_the_import(service_source):
    assert "fields." not in service_source, "the import must add no field to any model"


def test_optional_targets_are_capability_checked(service_source):
    """Fields that may not exist on this database are probed, never assumed."""
    for field_name in ("credit_limit", "industry_id", "transaction_date"):
        guarded = f'"{field_name}" in ' in service_source or f'"{field_name}" not in ' in service_source
        assert guarded, f"{field_name} is written without a _fields capability check"
    assert "_fields" in service_source


def test_related_records_are_looked_up_never_created(service_tree):
    """Payment terms, industries, countries and states are resolved, not seeded."""
    for name in ("_resolve_payment_term", "_resolve_industry", "_resolve_country_state"):
        function = _function(service_tree, name)
        called = {
            node.func.attr
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "search" in called, f"{name} does not look the record up"
        assert "create" not in called, f"{name} creates a record instead of resolving one"

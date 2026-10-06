"""Structural contract tests for the ERP import service.

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
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

SERVICE = ROOT / "plasticos_partner_import" / "models" / "erp_import_service.py"
DEAL_SERVICE = ROOT / "plasticos_transaction" / "models" / "legacy_erp_import_service.py"
RUNNER = ROOT / "plasticos_partner_import" / "scripts" / "run_erp_import.py"
ERP_PKG = ROOT / "plasticos_partner_import" / "erp"


@pytest.fixture(scope="module")
def service_source() -> str:
    return SERVICE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def service_tree(service_source: str) -> ast.Module:
    return ast.parse(service_source)


@pytest.fixture(scope="module")
def deal_source() -> str:
    return DEAL_SERVICE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def deal_tree(deal_source: str) -> ast.Module:
    return ast.parse(deal_source)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined in the import service")


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------
def test_service_is_wired_into_the_module(service_source):
    init = (ROOT / "plasticos_partner_import" / "models" / "__init__.py").read_text(encoding="utf-8")
    assert "from . import erp_import_service" in init
    assert '_name = "plasticos.erp.import"' in service_source


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
    for path in sorted(ERP_PKG.glob("*.py")):
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
        assert not isinstance(node, ast.ImportFrom) or "legacy_erp" not in (node.module or "")


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
        assert "legacy_erp_" in rendered


# ---------------------------------------------------------------------------
# Atomicity (gap G09)
# ---------------------------------------------------------------------------
def test_each_buysellno_is_wrapped_in_a_savepoint(deal_tree):
    loop = _function(deal_tree, "_import_transactions")
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


def test_commit_never_happens_inside_a_transaction_unit(deal_tree):
    loop = _function(deal_tree, "_import_transactions")
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
    calls = [
        node
        for node in ast.walk(upsert)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("create", "_write_identity_marker")
    ]
    assert len(calls) == 2, "the record and its identity marker"

    record_create, marker_write = sorted(calls, key=lambda n: n.lineno)
    # The record is created first; the ir.model.data marker follows it.
    assert record_create.func.attr == "create"
    assert isinstance(record_create.func.value, ast.Name)
    assert record_create.func.value.id == "model"
    assert marker_write.func.attr == "_write_identity_marker"
    assert record_create.lineno < marker_write.lineno

    marker = _function(service_tree, "_write_identity_marker")
    marker_creates = [
        node
        for node in ast.walk(marker)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "create"
    ]
    assert len(marker_creates) == 1
    assert "ir.model.data" in ast.dump(marker_creates[0].func.value)


def test_failed_transaction_is_recorded_and_the_run_continues(deal_tree):
    loop = _function(deal_tree, "_import_transactions")
    handlers = [node for node in ast.walk(loop) if isinstance(node, ast.ExceptHandler)]
    assert handlers, "a failing BuySellNo must be recorded, not abort the run"
    handler_body = ast.dump(handlers[0])
    assert "error" in handler_body
    assert "Continue" in handler_body or "continue" in handler_body.lower()


# ---------------------------------------------------------------------------
# Idempotency (gap G10)
# ---------------------------------------------------------------------------
def test_every_persisted_entity_goes_through_the_deterministic_upsert(service_tree):
    """No mapper may call ``create`` directly and bypass identity resolution.

    ``_write_identity_marker`` only writes ``ir.model.data`` (pinned by the
    marker-ordering test), so it is the one other allowed ``create`` site.
    ``Command.create`` is a one2many child line written onto a record that
    already went through ``_upsert``; it is not a standalone record.
    """
    allowed = {_function(service_tree, "_upsert"), _function(service_tree, "_write_identity_marker")}
    for node in ast.walk(service_tree):
        if not isinstance(node, ast.FunctionDef) or node in allowed:
            continue
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "create"):
                continue
            if isinstance(call.func.value, ast.Name) and call.func.value.id == "Command":
                continue
            raise AssertionError(f"{node.name} calls create() outside _upsert")


def test_upsert_writes_only_what_actually_changed(service_tree):
    """A second run must report ``skipped``, not churn every record."""
    upsert = ast.dump(_function(service_tree, "_upsert"))
    assert "_differs" in upsert
    assert "skipped" in upsert


def test_change_detection_compares_the_values_odoo_normalizes_on_write(service_tree, service_source):
    """An Html note gains <p> tags and a website gains its scheme on write; a replay must see no change."""
    differs = ast.get_source_segment(service_source, _function(service_tree, "_differs"))
    assert "html" in differs and "_plain_text" in differs
    assert "website" in differs and "_bare_url" in differs
    assert "html2plaintext" in service_source


def test_contact_role_tags_are_applied_as_a_set(service_tree):
    """Tag membership is set semantics, so replaying CRA_ID adds no duplicate."""
    apply_roles = ast.dump(_function(service_tree, "_apply_contact_roles"))
    assert "existing" in apply_roles and "missing" in apply_roles


# ---------------------------------------------------------------------------
# Existing-field policy
# ---------------------------------------------------------------------------
def test_no_new_field_is_declared_by_the_import(service_source):
    assert "fields." not in service_source, "the import must add no field to any model"


def test_optional_targets_are_capability_checked(service_source, deal_source):
    """Fields that may not exist on this database are probed, never assumed."""
    for field_name in ("credit_limit", "industry_id"):
        guarded = f'"{field_name}" in ' in service_source or f'"{field_name}" not in ' in service_source
        assert guarded, f"{field_name} is written without a _fields capability check"
    assert "_fields" in service_source
    assert '"transaction_date" in ' in deal_source


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


# ---------------------------------------------------------------------------
# Full-run completeness, validation before commit, import context
# ---------------------------------------------------------------------------
def _calls_in_order(function: ast.FunctionDef, names: tuple[str, ...]) -> list[str]:
    found = []
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in names:
            found.append((node.lineno, node.col_offset, node.func.attr))
    return [name for _line, _col, name in sorted(found)]


def test_full_run_executes_every_partner_stage_before_transactions(service_tree):
    """The default full importer must not skip roles and salespersons."""
    run = _function(service_tree, "run")
    stages = (
        "_import_counterparties",
        "_import_addresses",
        "_import_contacts",
        "_import_roles",
        "_import_sales_reps",
        "_extend_historical_import",
    )
    order = _calls_in_order(run, stages)
    assert order == list(stages), f"full run calls stages in order {order}"
    # Roles and salespersons are not guarded by partners_only.
    for node in ast.walk(run):
        if isinstance(node, ast.If) and "partners_only" in ast.dump(node.test):
            guarded = ast.dump(node.body[0]) if node.body else ""
            assert "_import_roles" not in guarded and "_import_sales_reps" not in guarded


def test_every_partner_stage_is_followed_by_the_after_stage_hook(service_tree):
    run = _function(service_tree, "run")
    hooked = [
        node.args[0].value
        for node in ast.walk(run)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "stage_done"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert hooked == ["counterparties", "addresses", "contacts", "roles", "salesreps"]
    # The hook runs before the single partner commit, and the layer path hooks its own stage.
    source = ast.get_source_segment(SERVICE.read_text(encoding="utf-8"), run)
    assert source.index('stage_done("salesreps")') < source.index("self.env.cr.commit()")
    assert source.index("stage_done(layer)") < source.index("self.env.cr.commit()")


def test_partner_writes_always_carry_the_import_context(service_source):
    """No helper may fall back to a bare environment and trigger chatter or automation."""
    lines = service_source.splitlines()
    read_only_markers = ("._fields", "active_test=False)")
    bare = [
        (number, line.strip())
        for number, line in enumerate(lines, start=1)
        if "self.env[RES_PARTNER]" in line
        and "IMPORT_CONTEXT" not in line
        and not any(marker in line for marker in read_only_markers)
    ]
    assert not bare, f"res.partner reached without IMPORT_CONTEXT: {bare}"
    # Read-only accessors (field capability probes, the address catalog) are the only bare ones.
    read_only = [
        number
        for number, line in enumerate(lines, start=1)
        if "self.env[RES_PARTNER]" in line and "IMPORT_CONTEXT" not in line
    ]
    assert len(read_only) == 3
    for name in ("_fill_company_from_contact", "_apply_site_mailbox"):
        function = ast.get_source_segment(service_source, _function(ast.parse(service_source), name))
        assert "IMPORT_CONTEXT" in function, f"{name} writes a partner without the import context"


def test_every_source_row_in_roles_and_sales_reps_receives_one_outcome(service_tree):
    """Set-valued writes collapse rows; the accounting must still credit each row."""
    roles = ast.dump(_function(service_tree, "_apply_contact_roles"))
    assert "credited" in roles and "skipped" in roles and "created" in roles
    import_roles = ast.dump(_function(service_tree, "_import_roles"))
    assert "roles_by_contact" in import_roles, "iterate the linked rows; violation rows are already reported"
    assert "reject" in import_roles, "an unmapped role word is a rejected row, not a silent anomaly"
    reps = ast.dump(_function(service_tree, "_import_sales_reps"))
    assert "len(rows)" in ast.get_source_segment(
        SERVICE.read_text(encoding="utf-8"), _function(service_tree, "_import_sales_reps")
    )
    assert "'user_id': False" in reps or '"user_id": False' in ast.get_source_segment(
        SERVICE.read_text(encoding="utf-8"), _function(service_tree, "_import_sales_reps")
    ), "a company whose source names no default rep must drop a stale Salesperson"


def test_superseded_people_and_stale_mailbox_markers_are_retired_not_left_visible(service_tree):
    alias = ast.dump(_function(service_tree, "_alias_xmlid"))
    assert "_retire_superseded_partner" in alias
    retire = ast.get_source_segment(
        SERVICE.read_text(encoding="utf-8"), _function(service_tree, "_retire_superseded_partner")
    )
    assert '"active": False' in retire and "unlink" not in retire, "retire by archiving, never by deleting"
    contacts = ast.dump(_function(service_tree, "_import_contacts"))
    assert contacts.count("_retire_stale_contact") == 2, "non-person and mailbox rows both retire a stale person"
    stale = ast.get_source_segment(
        SERVICE.read_text(encoding="utf-8"), _function(service_tree, "_retire_stale_contact")
    )
    assert "data.unlink()" in stale and '"active": False' in stale


def test_brokerage_mailboxes_are_dropped_at_the_mapping_seam(service_source):
    assert "external_emails" in service_source
    for raw in ('_text(row, "Email")', '_text(row, "BillingEmail")'):
        assert raw not in service_source, f"{raw} bypasses the internal-mailbox filter"


def test_partner_import_runtime_does_not_name_layer5_models():
    """Partner import may keep source-disposition catalogs. It may not call Layer 5."""
    runtime = ROOT / "plasticos_partner_import" / "models"
    for path in runtime.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "plasticos.transaction" not in text, path.name
    manifest = ast.literal_eval((ROOT / "plasticos_partner_import" / "__manifest__.py").read_text(encoding="utf-8"))
    assert "plasticos_transaction" not in manifest["depends"]
    assert "plasticos_crm_bridge" not in manifest["depends"]


def test_deal_realization_extends_the_partner_importer(deal_source, deal_tree):
    """Layer 5 consumes the Layer 3 importer. It does not own a second reader."""
    manifest = ast.literal_eval((ROOT / "plasticos_transaction" / "__manifest__.py").read_text(encoding="utf-8"))
    assert "plasticos_partner_import" in manifest["depends"]
    assert '_inherit = "plasticos.erp.import"' in deal_source
    assert '_name = "plasticos.' not in deal_source
    init = (ROOT / "plasticos_transaction" / "models" / "__init__.py").read_text(encoding="utf-8")
    assert "from . import legacy_erp_import_service" in init
    extend = _function(deal_tree, "_extend_historical_import")
    called = {
        node.func.attr
        for node in ast.walk(extend)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_import_transactions" in called
    assert "reconstruct_all_headers" in ast.dump(extend)
    assert "import csv" not in deal_source
    assert "run_csv_import" not in deal_source

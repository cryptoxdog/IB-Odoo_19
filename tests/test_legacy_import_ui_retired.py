"""Legacy ERP CSV partner-import UI retirement — pure-Python source guard.

Runs in the Odoo-free CI tier. It proves, from the module sources alone, that
the legacy CSV import has no UI entry point left (Settings block, wizard action
/ view, menu, button), that ordinary users hold no ACL on the retired wizard,
that every wizard execution action is closed behind the retirement guard, that
the upgrade migration matches the manifest version, and that the importer
code the UI used to drive is preserved. The Odoo-runtime twin is
``tests/test_partner_import_csv_paths.py``.
"""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import defusedxml.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plasticos_partner_import"
WIZARD_MODEL = "plasticos.partner.import.wizard"
WIZARD_MODEL_XMLID = "model_plasticos_partner_import_wizard"
RETIRED_DATA_FILES = ("views/res_config_settings_views.xml", "views/partner_import_wizard_views.xml")
RETIRED_XML_IDS = (
    "res_config_settings_view_form_partner_import",
    "action_partner_import_wizard",
    "view_partner_import_wizard_form",
)
RETIRED_SETTINGS_BUTTON = "action_plasticos_partner_import_run_default"
RETIRED_WIZARD_ACTIONS = ("action_import", "action_audit_import", "action_repair_import")
GUARD = "_ensure_legacy_ui_retired"


def _manifest() -> dict:
    return ast.literal_eval((MODULE / "__manifest__.py").read_text(encoding="utf-8"))


def _module_xml_files() -> list[Path]:
    return sorted(p for p in MODULE.rglob("*.xml") if "erp_extracted_data" not in p.parts)


def _class_def(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"method {name} not found on {cls.name}")


# ---------------------------------------------------------------------------
# Manifest / data files
# ---------------------------------------------------------------------------
def test_retired_data_files_are_neither_declared_nor_present():
    data = _manifest()["data"]
    for rel in RETIRED_DATA_FILES:
        assert rel not in data, f"{rel} still declared in __manifest__.py"
        assert not (MODULE / rel).exists(), f"{rel} still on disk"
    assert not (MODULE / "models" / "res_config_settings.py").exists()


def test_models_init_no_longer_imports_settings_glue():
    init = (MODULE / "models" / "__init__.py").read_text(encoding="utf-8")
    assert "res_config_settings" not in init


def test_upgrade_migration_matches_manifest_version():
    version = _manifest()["version"]
    script = MODULE / "migrations" / version / "post-migrate.py"
    assert script.exists(), f"migrations/{version}/post-migrate.py must exist so the upgrade retires persisted records"
    source = script.read_text(encoding="utf-8")
    for xml_id in RETIRED_XML_IDS:
        assert f'"{xml_id}"' in source, xml_id
    # The stored CSV-path parameters are preserved, never deleted by the upgrade.
    assert "ir_config_parameter" not in source
    assert "set_param" not in source
    tree = ast.parse(source)
    migrate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "migrate")
    assert [a.arg for a in migrate.args.args] == ["cr", "version"]


# ---------------------------------------------------------------------------
# XML: no entry point survives
# ---------------------------------------------------------------------------
def test_no_xml_entry_point_targets_the_legacy_import():
    for path in _module_xml_files():
        root = ET.parse(path).getroot()
        for record in root.iter("record"):
            assert record.get("id") not in RETIRED_XML_IDS, f"{path}: {record.get('id')}"
            model = record.get("model")
            if model in ("ir.actions.act_window", "ir.actions.server"):
                res_model = record.find("field[@name='res_model']")
                binding = record.find("field[@name='model_id']")
                assert res_model is None or (res_model.text or "").strip() != WIZARD_MODEL, path
                assert binding is None or WIZARD_MODEL_XMLID not in (binding.get("ref") or ""), path
            if model == "ir.ui.view":
                view_model = record.find("field[@name='model']")
                target = (view_model.text or "").strip() if view_model is not None else ""
                assert target not in (WIZARD_MODEL, "res.config.settings"), f"{path}: {record.get('id')}"
        for menu in root.iter("menuitem"):
            assert "partner_import_wizard" not in (menu.get("action") or ""), path
        for button in root.iter("button"):
            assert button.get("name") != RETIRED_SETTINGS_BUTTON, path
            assert button.get("name") not in RETIRED_WIZARD_ACTIONS, path


# ---------------------------------------------------------------------------
# ACL: ordinary users hold nothing on the retired wizard
# ---------------------------------------------------------------------------
def test_wizard_acl_is_system_only():
    with (MODULE / "security" / "ir.model.access.csv").open(encoding="utf-8", newline="") as fh:
        rows = [row for row in csv.DictReader(fh) if row["model_id:id"] == WIZARD_MODEL_XMLID]
    assert rows, "the retained wizard model still needs an ACL row (system only)"
    for row in rows:
        assert row["group_id:id"] == "base.group_system", row
    assert not [row for row in rows if row["group_id:id"] == "base.group_user"]


# ---------------------------------------------------------------------------
# Wizard: execution boundary closed, code preserved
# ---------------------------------------------------------------------------
def test_wizard_execution_actions_are_closed_behind_the_retirement_guard():
    source = (MODULE / "wizards" / "partner_import_wizard.py").read_text(encoding="utf-8")
    cls = _class_def(ast.parse(source), "PartnerImportWizard")
    guard = _method(cls, GUARD)
    raises = [n for n in ast.walk(guard) if isinstance(n, ast.Raise)]
    assert raises and isinstance(raises[0].exc, ast.Call) and raises[0].exc.func.id == "UserError"
    assert not any(isinstance(n, ast.If) for n in ast.walk(guard)), "the guard must be unconditional"
    for name in RETIRED_WIZARD_ACTIONS:
        first = _method(cls, name).body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            first = _method(cls, name).body[1]  # skip the docstring
        assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call), name
        func = first.value.func
        assert isinstance(func, ast.Attribute) and func.attr == GUARD, f"{name} must call {GUARD} first"


def _first_statement(func: ast.FunctionDef) -> ast.stmt:
    first = func.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        return func.body[1]  # skip the docstring
    return first


def test_service_import_entry_points_are_guarded_against_rpc_callers():
    """Public AbstractModel methods are RPC-reachable; the mutating ones must check the operator first."""
    service_tree = ast.parse((MODULE / "models" / "partner_import_service.py").read_text(encoding="utf-8"))
    service = _class_def(service_tree, "PlasticosPartnerImportService")
    guard = _method(service, "_check_import_operator")
    raises = [n for n in ast.walk(guard) if isinstance(n, ast.Raise)]
    assert raises and isinstance(raises[0].exc, ast.Call) and raises[0].exc.func.id == "AccessError"
    for name in ("run_full_import", "run_csv_import", "run_default_csv_import"):
        first = _first_statement(_method(service, name))
        assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call), name
        func = first.value.func
        assert isinstance(func, ast.Attribute) and func.attr == "_check_import_operator", name

    validation_tree = ast.parse((MODULE / "models" / "validation.py").read_text(encoding="utf-8"))
    repair = _method(_class_def(validation_tree, "PlasticosPartnerImportValidation"), "repair_import_data")
    first = _first_statement(repair)
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
    assert isinstance(first.value.func, ast.Attribute) and first.value.func.attr == "_check_import_operator"


def test_importer_logic_is_preserved_for_shell_reuse():
    service = (MODULE / "models" / "partner_import_service.py").read_text(encoding="utf-8")
    for method in ("def run_csv_import(", "def run_default_csv_import(", "def resolve_default_csv_path("):
        assert method in service, method
    shell = (MODULE / "scripts" / "run_import.py").read_text(encoding="utf-8")
    assert "def run_csv(" in shell and "run_csv_import" in shell
    assert (MODULE / "models" / "validation.py").exists()
    assert (MODULE / "wizards" / "partner_import_wizard.py").exists()
    assert "from . import partner_import_wizard" in (MODULE / "wizards" / "__init__.py").read_text(encoding="utf-8")
    # Canonical direct-SQL importer untouched by the retirement.
    assert (MODULE / "models" / "erp_import_service.py").exists()
    assert (MODULE / "scripts" / "import_erp_shell.py").exists()

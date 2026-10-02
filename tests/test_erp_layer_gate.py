"""ERP partner layer gate: the shell driver runs the layer validator (no Odoo runtime).

``import_erp_shell.py`` must refuse a layer until the previous layer's
validator passes, and must exit with the layer's own validator result. The
driver runs here against stubbed ``odoo.addons`` modules; the validator's gate
order is loaded from the real file. Every dataset fact the validator reads from
``partner_layer_expectations.json`` must exist there.
"""

import ast
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plasticos_partner_import" / "scripts"
DRIVER = SCRIPTS / "import_erp_shell.py"
VALIDATOR = SCRIPTS / "validate_partner_layer.py"
SERVICE = ROOT / "plasticos_partner_import" / "models" / "erp_import_service.py"
PACKAGE = "odoo.addons.plasticos_partner_import.scripts"


def _real_validator():
    spec = importlib.util.spec_from_file_location("erp_validate_partner_layer", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Cursor:
    def __init__(self):
        self.queries = []

    def execute(self, query):
        self.queries.append(query)

    def fetchone(self):
        return (0,)


class _Env:
    def __init__(self):
        self.cr = _Cursor()


class _Harness:
    def __init__(self, monkeypatch, failing=()):
        self.validated = []
        self.runs = []
        self.env = _Env()
        real = _real_validator()

        def validate(env, layer):
            self.validated.append(layer)
            return 1 if layer in failing else 0

        def run(env, **kwargs):
            self.runs.append(kwargs)
            return {"summary": {"final_status": "succeeded"}}

        for name in ("odoo", "odoo.addons", "odoo.addons.plasticos_partner_import", PACKAGE):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        runner = types.ModuleType(f"{PACKAGE}.run_erp_import")
        runner.run = run
        validator = types.ModuleType(f"{PACKAGE}.validate_partner_layer")
        validator.LAYER_BEFORE = real.LAYER_BEFORE
        validator.validate = validate
        monkeypatch.setitem(sys.modules, runner.__name__, runner)
        monkeypatch.setitem(sys.modules, validator.__name__, validator)
        for name in ("DRY", "LIMIT", "PAYLOAD_ROOT", "REPORT_PATH", "PARTNERS_ONLY", "LAYER", "REQUIRE_EMPTY"):
            monkeypatch.delenv(f"ERP_{name}", raising=False)

    def main(self):
        namespace = {"__name__": "erp_import_shell", "env": self.env}
        exec(compile(DRIVER.read_text(encoding="utf-8"), str(DRIVER), "exec"), namespace)  # noqa: S102
        return namespace["main"]()


def test_gate_order_covers_every_import_layer_and_names_real_checks():
    real = _real_validator()
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    layers = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PARTNER_LAYERS" for t in node.targets)
    )
    assert tuple(real.LAYER_BEFORE) == layers
    assert set(real.LAYER_BEFORE.values()) <= set(real.CHECKS)
    assert set(layers) <= set(real.CHECKS)


def test_layer_is_refused_when_the_previous_validator_fails(monkeypatch):
    harness = _Harness(monkeypatch, failing={"counterparties"})
    monkeypatch.setenv("ERP_LAYER", "addresses")

    assert harness.main() == 1
    assert harness.validated == ["counterparties"]
    assert harness.runs == []


def test_layer_exit_code_is_its_own_validator(monkeypatch):
    harness = _Harness(monkeypatch, failing={"addresses"})
    monkeypatch.setenv("ERP_LAYER", "addresses")

    assert harness.main() == 1
    assert harness.validated == ["counterparties", "addresses"]
    assert harness.runs[0]["layer"] == "addresses"
    assert harness.runs[0]["partners_only"] is True


def test_first_layer_is_gated_by_the_database_check_and_the_empty_partner_check(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "counterparties")

    assert harness.main() == 0
    assert harness.validated == ["database", "counterparties"]
    assert harness.env.cr.queries


def test_later_layers_do_not_require_an_empty_partner_set(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "contacts")

    assert harness.main() == 0
    assert harness.validated == ["addresses", "contacts"]
    assert harness.env.cr.queries == []


def test_dry_run_layer_runs_no_validator(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "roles")
    monkeypatch.setenv("ERP_DRY", "1")

    assert harness.main() == 0
    assert harness.validated == []
    assert harness.runs[0]["dry_run"] is True


def test_unknown_layer_is_rejected_before_any_import(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "database")

    with pytest.raises(SystemExit):
        harness.main()
    assert harness.runs == []


def _resolve(node, scope, data):
    """JSON values ``node`` reads: ``_expect()``, a tracked name, or a string subscript of either."""
    if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_expect":
        return [data]
    if isinstance(node, ast.Name):
        return scope.get(node.id)
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        parents = _resolve(node.value, scope, data)
        if parents is None:
            return None
        key = node.slice.value
        for parent in parents:
            assert isinstance(parent, dict) and key in parent, f"line {node.lineno}: expectation key {key!r} is missing"
        return [parent[key] for parent in parents]
    return None


def test_every_expectation_the_validator_reads_exists():
    data = json.loads((SCRIPTS / "partner_layer_expectations.json").read_text(encoding="utf-8"))
    tree = ast.parse(VALIDATOR.read_text(encoding="utf-8"))
    reads = 0
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        scope: dict = {}
        for node in sorted(ast.walk(function), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0))):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                values = _resolve(node.value, scope, data)
                if values is not None:
                    scope[node.targets[0].id] = values
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                values = _resolve(node.iter, scope, data)
                if values is not None:
                    scope[node.target.id] = [item for value in values for item in value]
            elif isinstance(node, ast.Subscript) and _resolve(node, scope, data) is not None:
                reads += 1
    assert reads > 20


def test_makefile_forwards_the_layer_to_both_runtimes():
    target = (ROOT / "Makefile").read_text(encoding="utf-8").split("\nimport-erp:", 1)[1].split("\n\n", 1)[0]
    assert target.count('ERP_LAYER="$(ERP_LAYER)"') == 2
    assert target.count('ERP_PARTNERS_ONLY="$(ERP_PARTNERS_ONLY)"') == 2

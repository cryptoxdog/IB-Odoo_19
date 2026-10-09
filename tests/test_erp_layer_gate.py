"""ERP partner layer gate: the shell driver validates every stage before it commits (no Odoo runtime).

``import_erp_shell.py`` must run the database check before anything writes,
refuse a layer until the previous layer's validator passes, validate each stage
it wrote **before** the commit, and roll the stage back when that validator
fails. The driver runs here against stubbed ``odoo.addons`` modules; the
validator's gate order is loaded from the real file. Every dataset fact the
validator reads from ``partner_layer_expectations.json`` must exist there, and
the validator must read the source the import read, never a bundled CSV.
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
ERP_PACKAGE = "odoo.addons.plasticos_partner_import.erp"
PARTNER_LAYERS = ("counterparties", "addresses", "contacts", "roles", "salesreps")


def _real_validator():
    spec = importlib.util.spec_from_file_location("erp_validate_partner_layer", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _excludes_localization_partners(query: str) -> bool:
    """The census SQL exempts only l10n_* ir.model.data rows, not every XMLID."""
    compact = " ".join(query.split())
    required = (
        "NOT EXISTS",
        "data.model = 'res.partner'",
        "data.res_id = partner.id",
        "LEFT(data.module, 5) = 'l10n_'",
    )
    return all(part in compact for part in required) and "LIKE" not in compact


class _Cursor:
    def __init__(self, partner_rows="empty"):
        self.queries = []
        self.commits = 0
        self.rollbacks = 0
        self.partner_rows = partner_rows

    def execute(self, query):
        self.queries.append(query)

    def fetchone(self):
        query = self.queries[-1]
        census = "res_users" in query
        if self.partner_rows == "business" and census:
            return (1,)
        if self.partner_rows == "localization_only" and census:
            # A census that still counts localization reference partners is the pre-repair bug.
            return (0,) if _excludes_localization_partners(query) else (15,)
        if census:
            return (0,)
        return (28,)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Env:
    def __init__(self, partner_rows="empty"):
        self.cr = _Cursor(partner_rows)


class _Harness:
    """Stub the Odoo-side modules the driver imports; record what it validated, ran, and committed."""

    def __init__(self, monkeypatch, failing=(), database=None, partner_rows="empty", odoo_env=None):
        self.validated = []
        self.validated_payloads = []
        self.runs = []
        self.source_lookups = []
        self.env = odoo_env if odoo_env is not None else _Env(partner_rows)
        real = _real_validator()
        harness = self

        def validate(env, layer, payload=None):
            harness.validated.append(layer)
            harness.validated_payloads.append(payload)
            return 1 if layer in failing else 0

        def run(env, **kwargs):
            harness.runs.append(kwargs)
            hook = kwargs.get("after_stage")
            stages = (kwargs["layer"],) if kwargs.get("layer") else PARTNER_LAYERS
            payload = object()
            # The real service calls the hook after each stage and commits only when every hook passed.
            if hook is not None:
                for stage in stages:
                    hook(stage, payload)
            if kwargs.get("commit") and not kwargs.get("dry_run"):
                env.cr.commit()
            return {"summary": {"final_status": "success"}}

        for name in ("odoo", "odoo.addons", "odoo.addons.plasticos_partner_import", PACKAGE, ERP_PACKAGE):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        reader = types.ModuleType(f"{ERP_PACKAGE}.reader")

        def database_source_from_env(environ):
            harness.source_lookups.append(environ)
            return database

        reader.database_source_from_env = database_source_from_env
        runner = types.ModuleType(f"{PACKAGE}.run_erp_import")
        runner.run = run
        validator = types.ModuleType(f"{PACKAGE}.validate_partner_layer")
        validator.LAYER_BEFORE = real.LAYER_BEFORE
        validator.DATABASE_CHECK = real.DATABASE_CHECK
        validator.LayerRejected = real.LayerRejected
        validator.validate = validate
        validator.check_full_run_extension = real.check_full_run_extension
        monkeypatch.setitem(sys.modules, reader.__name__, reader)
        monkeypatch.setitem(sys.modules, runner.__name__, runner)
        monkeypatch.setitem(sys.modules, validator.__name__, validator)
        for name in (
            "DRY",
            "LIMIT",
            "PAYLOAD_ROOT",
            "REPORT_PATH",
            "PARTNERS_ONLY",
            "LAYER",
            "REQUIRE_EMPTY",
            "TARGET_DB",
        ):
            monkeypatch.delenv(f"ERP_{name}", raising=False)

    def main(self):
        """Load the real driver the same way as the validator: a fixed repo file, not evaluated text."""
        spec = importlib.util.spec_from_file_location("erp_import_shell_under_test", DRIVER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # ``odoo shell`` injects ``env`` into the script globals. The driver reads that name.
        module.env = self.env
        return module.main()


def test_gate_order_covers_every_import_layer_and_names_real_checks():
    real = _real_validator()
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    layers = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PARTNER_LAYERS" for t in node.targets)
    )
    assert tuple(real.LAYER_BEFORE) == layers == PARTNER_LAYERS
    assert set(real.LAYER_BEFORE.values()) <= set(real.CHECKS)
    assert set(layers) <= set(real.CHECKS)


def test_database_check_runs_before_anything_is_imported(monkeypatch):
    harness = _Harness(monkeypatch, failing={"database"})
    monkeypatch.setenv("ERP_PARTNERS_ONLY", "1")

    assert harness.main() == 1
    assert harness.validated == ["database"]
    assert harness.runs == []
    assert harness.env.cr.commits == 0


def test_layer_is_refused_when_the_previous_validator_fails(monkeypatch):
    harness = _Harness(monkeypatch, failing={"counterparties"})
    monkeypatch.setenv("ERP_LAYER", "addresses")

    assert harness.main() == 1
    assert harness.validated == ["database", "counterparties"]
    assert harness.runs == []
    assert harness.env.cr.commits == 0


def test_failing_layer_validator_rolls_the_stage_back_before_any_commit(monkeypatch):
    harness = _Harness(monkeypatch, failing={"addresses"})
    monkeypatch.setenv("ERP_LAYER", "addresses")

    assert harness.main() == 1
    assert harness.validated == ["database", "counterparties", "addresses"]
    assert harness.runs[0]["layer"] == "addresses"
    assert harness.runs[0]["partners_only"] is True
    assert harness.env.cr.commits == 0, "a failed layer must never be persisted"
    assert harness.env.cr.rollbacks == 1


def test_passing_layer_validator_is_run_against_the_imported_payload_then_committed(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "roles")

    assert harness.main() == 0
    assert harness.validated == ["database", "contacts", "roles"]
    # The stage validator receives the payload the import read, not a file it opens itself.
    assert harness.validated_payloads[-1] is not None
    assert harness.env.cr.commits == 1
    assert harness.env.cr.rollbacks == 0


def test_full_partner_run_validates_every_stage_in_order_before_the_single_commit(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_PARTNERS_ONLY", "1")

    assert harness.main() == 0
    assert harness.validated == ["database", *PARTNER_LAYERS]
    assert harness.runs[0]["partners_only"] is True
    assert harness.runs[0]["layer"] is None
    assert harness.env.cr.commits == 1


def test_full_partner_run_stops_at_the_first_failing_stage(monkeypatch):
    harness = _Harness(monkeypatch, failing={"contacts"})
    monkeypatch.setenv("ERP_PARTNERS_ONLY", "1")

    assert harness.main() == 1
    assert harness.validated == ["database", "counterparties", "addresses", "contacts"]
    assert harness.env.cr.commits == 0
    assert harness.env.cr.rollbacks == 1


def test_first_layer_is_gated_by_the_database_check_and_the_empty_partner_check(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "counterparties")

    assert harness.main() == 0
    assert harness.validated == ["database", "counterparties"]
    assert harness.env.cr.queries, "the empty-partner guard must query the database"


def test_later_layers_do_not_require_an_empty_partner_set(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "contacts")

    assert harness.main() == 0
    assert harness.validated == ["database", "addresses", "contacts"]
    assert harness.env.cr.queries == []


def _business_census(queries):
    return next(query for query in queries if "res_users" in query)


def test_empty_partner_census_excludes_only_localization_owned_partners(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "counterparties")

    assert harness.main() == 0
    census = _business_census(harness.env.cr.queries)
    assert _excludes_localization_partners(census)
    assert "plasticos_" not in census


def test_preexisting_business_partner_refuses_before_the_importer_runs(monkeypatch):
    harness = _Harness(monkeypatch, partner_rows="business")
    monkeypatch.setenv("ERP_LAYER", "counterparties")

    with pytest.raises(SystemExit, match="business partner"):
        harness.main()
    assert harness.runs == []
    assert harness.env.cr.commits == 0


def test_localization_reference_partners_do_not_block_the_importer(monkeypatch):
    harness = _Harness(monkeypatch, partner_rows="localization_only")
    monkeypatch.setenv("ERP_LAYER", "counterparties")

    assert harness.main() == 0
    assert harness.runs, "a localization-only partner table must reach the importer"
    assert harness.runs[0]["layer"] == "counterparties"
    assert _excludes_localization_partners(_business_census(harness.env.cr.queries))


def test_dry_run_validates_nothing_and_commits_nothing(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "roles")
    monkeypatch.setenv("ERP_DRY", "1")

    assert harness.main() == 0
    assert harness.validated == []
    assert harness.runs[0]["dry_run"] is True
    assert harness.runs[0]["after_stage"] is None
    assert harness.env.cr.commits == 0


def test_direct_database_source_is_handed_to_the_import(monkeypatch):
    sentinel = types.SimpleNamespace(label="erp-host/ERP_RESTORED")
    harness = _Harness(monkeypatch, database=sentinel)
    monkeypatch.setenv("ERP_PARTNERS_ONLY", "1")

    assert harness.main() == 0
    assert harness.runs[0]["database"] is sentinel


class _Modules:
    def __init__(self, installed):
        self.installed = installed
        self.searches = 0

    def search(self, domain):
        self.searches += 1
        wanted = next(value for name, _op, value in domain if name == "name")
        return types.SimpleNamespace(mapped=lambda _field: [m for m in wanted if m in self.installed])


class _DatabaseEnv:
    """Just enough Odoo for ``check_database``: name, modules, registry, contact form."""

    def __init__(self, installed, models=("plasticos.transaction",), name="erp_import_gate"):
        cursor = _Cursor()
        cursor.fetchone = lambda: (name,)
        self.cr = cursor
        self.modules = _Modules(set(installed))
        self.models = set(models)

    def __getitem__(self, model):
        assert model == "ir.module.module"
        return self.modules

    def __contains__(self, model):
        return model in self.models

    def ref(self, _xmlid, raise_if_not_found=True):
        return types.SimpleNamespace(get_combined_arch=lambda: "phone_line_ids not is_company")


def _database_failures(monkeypatch, env, **settings):
    real = _real_validator()
    for name in ("PARTNERS_ONLY", "LAYER"):
        monkeypatch.delenv(f"ERP_{name}", raising=False)
    monkeypatch.setenv("ERP_TARGET_DB", "erp_import_gate")
    monkeypatch.delenv("ODOO_STAGE", raising=False)
    for name, value in settings.items():
        monkeypatch.setenv(f"ERP_{name}", value)
    failures: list[str] = []
    real.check_database(env, failures)
    return failures


PARTNER_RUNTIME = (*_real_validator().USA_MODULES, "plasticos_partner_import")
FULL_RUN = _real_validator().FULL_RUN_MODULES


def test_full_import_needs_the_native_document_modules(monkeypatch):
    failures = _database_failures(monkeypatch, _DatabaseEnv(PARTNER_RUNTIME, models=()))
    assert failures == [
        "full import needs installed modules: sale, purchase, account, plasticos_transaction, plasticos_accounting"
    ]


def test_full_import_proceeds_when_native_document_modules_are_installed(monkeypatch):
    env = _DatabaseEnv((*PARTNER_RUNTIME, *FULL_RUN))
    assert _database_failures(monkeypatch, env) == []


@pytest.mark.parametrize(
    "settings",
    [{"PARTNERS_ONLY": "1"}, *({"LAYER": layer} for layer in PARTNER_LAYERS)],
    ids=["partners_only", *PARTNER_LAYERS],
)
def test_concern1_runs_do_not_require_the_transaction_module(monkeypatch, settings):
    env = _DatabaseEnv(PARTNER_RUNTIME, models=())
    assert _database_failures(monkeypatch, env, **settings) == []


def test_standalone_database_preflight_keeps_the_full_run_requirement(monkeypatch):
    """``ERP_LAYER=database`` selects the check itself; it is not a partner-only scope."""
    failures = _database_failures(monkeypatch, _DatabaseEnv(PARTNER_RUNTIME, models=()), LAYER="database")
    assert failures == [
        "full import needs installed modules: sale, purchase, account, plasticos_transaction, plasticos_accounting"
    ]


def test_full_dry_run_is_refused_before_import(monkeypatch, capsys):
    """A full preview on a database without the document modules must not report success or call the importer."""
    env = _DatabaseEnv((*PARTNER_RUNTIME, "plasticos_transaction"))
    harness = _Harness(monkeypatch, odoo_env=env)
    monkeypatch.setenv("ERP_DRY", "1")

    assert harness.main() == 1
    assert harness.runs == []
    assert harness.validated == []
    assert harness.source_lookups == []
    assert harness.env.cr.commits == 0
    assert harness.env.cr.queries == []
    assert (
        "full import needs installed modules: sale, purchase, account, plasticos_accounting" in capsys.readouterr().out
    )


def test_full_dry_run_proceeds_on_a_complete_database(monkeypatch):
    """The preflight reads the installed set from ``env``; a complete database previews the full import."""
    env = _DatabaseEnv((*PARTNER_RUNTIME, *FULL_RUN))
    harness = _Harness(monkeypatch, odoo_env=env)
    monkeypatch.setenv("ERP_DRY", "1")

    assert harness.main() == 0
    assert env.modules.searches == 1
    assert harness.runs[0]["dry_run"] is True
    assert harness.runs[0]["partners_only"] is False
    assert harness.env.cr.commits == 0


@pytest.mark.parametrize(
    "settings",
    [{"PARTNERS_ONLY": "1"}, {"LAYER": "roles"}],
    ids=["partners_only", "layer"],
)
def test_partner_scoped_dry_runs_do_not_require_the_transaction_extension(monkeypatch, settings):
    """Concern 1 previews stay preflight-free on a database with no transaction extension."""
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_DRY", "1")
    for name, value in settings.items():
        monkeypatch.setenv(f"ERP_{name}", value)

    assert harness.main() == 0
    assert harness.validated == []
    assert harness.runs[0]["dry_run"] is True
    assert harness.runs[0]["after_stage"] is None
    assert harness.runs[0]["partners_only"] is True
    assert harness.env.cr.commits == 0


def test_full_import_without_transactions_is_refused_before_the_importer_runs(monkeypatch):
    """The driver's own database check refuses the run; no partner stage writes or commits."""
    harness = _Harness(monkeypatch)
    real = _real_validator()
    env = _DatabaseEnv(PARTNER_RUNTIME, models=())

    def validate(_env, layer, payload=None):
        harness.validated.append(layer)
        failures: list[str] = []
        real.CHECKS[layer](env, failures)
        return 1 if failures else 0

    sys.modules[f"{PACKAGE}.validate_partner_layer"].validate = validate
    monkeypatch.setenv("ERP_TARGET_DB", "erp_import_gate")

    assert harness.main() == 1
    assert harness.validated == ["database"]
    assert harness.runs == [], "a full import must not reach the importer"
    assert harness.env.cr.commits == 0


def test_full_import_with_a_failed_summary_exits_nonzero(monkeypatch):
    """A reconciliation gap makes the summary ``failed``; the driver must not exit 0 on it."""
    harness = _Harness(monkeypatch)
    runner = sys.modules[f"{PACKAGE}.run_erp_import"]
    passing = runner.run

    def run(env, **kwargs):
        passing(env, **kwargs)
        return {"summary": {"final_status": "failed"}}

    runner.run = run
    monkeypatch.setenv("ERP_PARTNERS_ONLY", "1")

    assert harness.main() == 1
    assert harness.runs[0]["partners_only"] is True


def test_unknown_layer_is_rejected_before_any_import(monkeypatch):
    harness = _Harness(monkeypatch)
    monkeypatch.setenv("ERP_LAYER", "database")

    with pytest.raises(SystemExit):
        harness.main()
    assert harness.runs == []


# ---------------------------------------------------------------------------
# Validator: bound to the active source, never to a bundled CSV or one DB name
# ---------------------------------------------------------------------------
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


def test_validator_reads_the_source_the_import_read_not_a_bundled_csv():
    source = VALIDATOR.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert "csv" not in imported, "the validator must not open CSV files on its own"
    assert "reader" in source and "load_payload" in source and "database_source_from_env" in source
    assert "PARTNER_SOURCE_TABLES" in source
    # The stage hook binds the checks to the very payload the import read.
    validate = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "validate")
    assert [arg.arg for arg in validate.args.args] == ["env", "layer", "payload"]


def test_validator_expects_no_single_database_name_and_derives_the_company_count_from_the_source():
    data = json.loads((SCRIPTS / "partner_layer_expectations.json").read_text(encoding="utf-8"))
    assert "database" not in data, "the proof database is declared per run (ERP_TARGET_DB), never pinned"
    assert "company_count" not in data, "the company count comes from the active source"
    source = VALIDATOR.read_text(encoding="utf-8")
    assert 'TARGET_DB_ENV = "ERP_TARGET_DB"' in source
    assert 'ODOO_STAGE_ENV = "ODOO_STAGE"' in source
    assert "erp_import_test" not in source
    tree = ast.parse(source)
    count = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_expected_company_count"
    )
    assert "_rows" in ast.dump(count) and "CompanyNm" in ast.dump(count)


def test_validator_does_not_require_an_invented_facility_role():
    source = VALIDATOR.read_text(encoding="utf-8")
    assert "facility_role" not in source
    graph_validator = (ROOT / "plasticos_partner_import" / "models" / "validation.py").read_text(encoding="utf-8")
    assert 'facility_role = "other"' not in graph_validator, "a facility role is never invented to satisfy a validator"
    assert 'missing facility_role")' not in graph_validator


def test_makefile_forwards_the_layer_to_both_runtimes():
    target = (ROOT / "Makefile").read_text(encoding="utf-8").split("\nimport-erp:", 1)[1].split("\n\n", 1)[0]
    assert target.count('ERP_LAYER="$(ERP_LAYER)"') == 2
    assert target.count('ERP_PARTNERS_ONLY="$(ERP_PARTNERS_ONLY)"') == 2
    assert target.count('ERP_TARGET_DB="$(ODOO_DB_NAME)"') == 2
    for name in (
        "ERP_SQL_SERVER",
        "ERP_SQL_DATABASE",
        "ERP_SQL_USER",
        "ERP_SQL_PASSWORD",
        "ERP_SQL_PORT",
        "ERP_SQL_DRIVER",
    ):
        assert target.count(f'{name}="$({name})"') == 2, f"{name} must reach both runtimes"

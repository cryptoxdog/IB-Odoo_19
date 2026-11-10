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
def test_deal_extension_does_not_write_the_transaction_object(deal_source):
    assert "_import_transactions" not in deal_source
    assert "_import_one_transaction" not in deal_source
    assert "legacy_erp_transaction_" not in deal_source
    assert "legacy_erp_detail_" not in deal_source
    extend = _function(ast.parse(deal_source), "_extend_historical_import")
    returns = [node for node in ast.walk(extend) if isinstance(node, ast.Return)]
    assert returns
    assert not (isinstance(returns[-1].value, ast.Constant) and returns[-1].value.value is False)


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


def test_erp_replay_keeps_crm_notes_appended_to_the_partner_comment(service_tree, service_source):
    """The CRM sync appends paragraphs to ``comment``; an ERP replay must neither drop nor repeat them."""
    from erp.comment_notes import comment_with_erp_notes

    upsert = ast.get_source_segment(service_source, _function(service_tree, "_upsert"))
    assert "_comment_with_erp_notes(record.comment" in upsert
    merge = comment_with_erp_notes
    stored = "<p>Ext 1187\next 1187</p><p>CRM history</p>"
    assert merge(stored, "Ext 1187\next 1187") is None
    assert merge("<p>Ext 1187</p><p>ext 1187</p><p>CRM history</p>", "Ext 1187\next 1187") is None
    assert merge("<p>CRM history</p>", "ERP & note") == "<p>ERP &amp; note</p><p>CRM history</p>"
    assert merge(False, "ERP note") == "ERP note"
    assert merge("<p>ERP note</p>", "") is None


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
    for field_name in ("credit_limit", "industry_id"):
        guarded = f'"{field_name}" in ' in service_source or f'"{field_name}" not in ' in service_source
        assert guarded, f"{field_name} is written without a _fields capability check"
    assert "_fields" in service_source


def test_trade_date_has_no_custom_transaction_field_or_misplaced_target(deal_tree):
    """GPLedger.TradeDt belongs on purchase.order.date_approve; the deal import neither writes nor anticipates
    a plasticos.transaction date field, and never parks the date in a pickup/delivery field."""
    keys = {
        node.value
        for node in ast.walk(deal_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isidentifier()
    }
    assert "transaction_date" not in keys
    assert not keys & {"expected_pickup_date", "actual_pickup_date", "expected_delivery_date", "actual_delivery_date"}
    trade_date_reads = [
        node for node in ast.walk(deal_tree) if isinstance(node, ast.Attribute) and node.attr == "trade_date"
    ]
    assert trade_date_reads == [], "the reconstructed trade date stays source evidence until PO realization"


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
    source = ast.get_source_segment(SERVICE.read_text(encoding="utf-8"), _function(service_tree, "_import_sales_reps"))
    assert "default_sales_rep" in source
    assert "'user_id': False" not in source and '"user_id": False' not in source, (
        "an unresolved rep must leave the existing Salesperson"
    )


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
    assert "_import_transactions" not in called
    assert "realize" in called
    assert "reconstruct_all_headers" not in ast.dump(extend)
    assert "import csv" not in deal_source
    assert "run_csv_import" not in deal_source


# ---------------------------------------------------------------------------
# Contact eligibility and channel fidelity: the REAL contact layer
# ---------------------------------------------------------------------------
# ``_import_contacts`` runs unmodified against an in-memory ORM. ``odoo`` is
# stubbed only while the service module loads, and the module is loaded under
# a private package name, so no other test sees the stub. Synthetic rows only.
import importlib.util  # noqa: E402
import re  # noqa: E402
import types  # noqa: E402


def _load_contact_service():
    stub = types.ModuleType("odoo")
    stub.Command = types.SimpleNamespace(create=lambda vals: (0, 0, vals), clear=lambda: (5, 0, 0))
    stub.api = types.SimpleNamespace(model=lambda fn: fn)
    stub.models = types.SimpleNamespace(AbstractModel=object)
    tools = types.ModuleType("odoo.tools")
    tools.html2plaintext = lambda value: re.sub(r"<[^>]+>", " ", str(value or ""))
    saved = {name: sys.modules.get(name) for name in ("odoo", "odoo.tools")}
    package = types.ModuleType("_erp_contact_pkg")
    package.__path__ = [str(ROOT / "plasticos_partner_import")]
    models_pkg = types.ModuleType("_erp_contact_pkg.models")
    models_pkg.__path__ = [str(ROOT / "plasticos_partner_import" / "models")]
    sys.modules.update({"odoo": stub, "odoo.tools": tools})
    sys.modules["_erp_contact_pkg"] = package
    sys.modules["_erp_contact_pkg.models"] = models_pkg
    try:
        spec = importlib.util.spec_from_file_location("_erp_contact_pkg.models.erp_import_service", SERVICE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return module


_PARTNER_FIELDS = {
    name: types.SimpleNamespace(type=kind)
    for name, kind in {
        "name": "char",
        "parent_id": "many2one",
        "is_company": "boolean",
        "type": "selection",
        "active": "boolean",
        "email": "char",
        "phone": "char",
        "comment": "html",
        "supplier_rank": "integer",
        "customer_rank": "integer",
        "company_role": "selection",
        "location_partner_ids": "many2many",
        "phone_line_ids": "one2many",
    }.items()
}


class _Empty:
    id = False
    ids: list = []

    def __bool__(self):
        return False

    def exists(self):
        return self

    def __getattr__(self, name):
        return False


class _Partner:
    _name = "res.partner"
    _fields = _PARTNER_FIELDS

    def __init__(self, rec_id, vals):
        self.id = rec_id
        self.name = self.type = self.parent_id = False
        self.email = self.phone = self.comment = self.company_role = False
        self.supplier_rank = self.customer_rank = 0
        self.is_company = False
        self.active = True
        self.phone_line_ids: list = []
        self.location_partner_ids = types.SimpleNamespace(ids=[])
        self.writes: list[dict] = []
        self._apply(vals)

    def _apply(self, vals):
        for key, value in vals.items():
            if key == "phone_line_ids":
                for _cmd, _id, line in value:
                    self.phone_line_ids.append(types.SimpleNamespace(**line))
            elif key == "location_partner_ids":
                self.location_partner_ids = types.SimpleNamespace(ids=list(value[0][2]))
            else:
                setattr(self, key, value)

    def __getitem__(self, name):
        return getattr(self, name)

    def with_context(self, **_ctx):
        return self

    def exists(self):
        return self

    def write(self, vals):
        self.writes.append(dict(vals))
        self._apply(vals)


class _PartnerModel:
    _name = "res.partner"
    _fields = _PARTNER_FIELDS

    def __init__(self):
        self.rows: dict[int, _Partner] = {}

    def with_context(self, **_ctx):
        return self

    def browse(self, rec_id=None):
        if isinstance(rec_id, list):
            return _PartnerSet(self.rows[rid] for rid in rec_id if rid in self.rows)
        return self.rows.get(rec_id) or _Empty()

    def create(self, vals):
        record = _Partner(len(self.rows) + 1, vals)
        self.rows[record.id] = record
        return record


class _PartnerSet(list):
    def exists(self):
        return self

    def filtered(self, fn):
        return _PartnerSet(row for row in self if fn(row))

    def write(self, vals):
        for row in self:
            row.write(vals)


class _MarkerSet(list):
    def unlink(self):
        for row in list(self):
            row.unlink()


class _Marker(types.SimpleNamespace):
    def write(self, vals):
        self.__dict__.update(vals)

    def unlink(self):
        self.store.remove(self)


class _MarkerModel:
    def __init__(self):
        self.rows: list[_Marker] = []

    def search(self, domain, limit=None):
        def hit(row):
            for field, op, value in domain:
                current = getattr(row, field)
                if op == "=like":
                    if not str(current).startswith(value.rstrip("%")):
                        return False
                elif op == "in":
                    if current not in value:
                        return False
                elif current != value:
                    return False
            return True

        hits = [row for row in self.rows if hit(row)]
        if limit == 1:
            return hits[0] if hits else _Empty()
        return _MarkerSet(hits)

    def create(self, vals):
        row = _Marker(store=self.rows, **vals)
        self.rows.append(row)
        return row

    def names(self):
        return sorted(row.name for row in self.rows)


class _ContactEnv(dict):
    def ref(self, xmlid, raise_if_not_found=True):
        return None


def _contact_run(rows, existing_company=None, earlier=None, roles=None):
    """Run the contact layer over ``rows`` for one counterparty.

    ``earlier`` maps a person name to the CT_IDs an earlier run stored for it.
    """
    from erp.report import ImportReport

    module = _load_contact_service()
    partners, markers = _PartnerModel(), _MarkerModel()
    company = partners.create({"name": "Synthetic Co", "is_company": True, **(existing_company or {})})
    for name, ct_ids in (earlier or {}).items():
        person = partners.create({"name": name, "parent_id": company.id})
        for ct_id in ct_ids:
            markers.create(
                {
                    "module": module.XMLID_MODULE,
                    "name": f"legacy_erp_contact_{ct_id}",
                    "model": "res.partner",
                    "res_id": person.id,
                    "noupdate": True,
                }
            )
    service = module.PlasticosErpImport()
    service.env = _ContactEnv({"res.partner": partners, "ir.model.data": markers})
    service._address_catalog = lambda: []
    contacts = {str(row["CT_ID"]): {"CpID": "C1", "Location": "", "Notes": "", **row} for row in rows}
    index = types.SimpleNamespace(
        contacts=contacts,
        contacts_by_cp={"C1": list(contacts)},
        roles_by_contact={ct: [f"R{ct}"] for ct in (roles or {})},
        contact_roles={f"R{ct}": {"RoleNm": role} for ct, role in (roles or {}).items()},
        addresses={},
        addresses_by_cp={},
        omitted_contact_ids=set(),
    )
    report = ImportReport()
    service._import_contacts(index, report, {"C1": company.id}, dry_run=False)
    people = [p for p in partners.rows.values() if not p.is_company]
    return people, markers, report, company, (service, index, partners)


def _contact_row(ct_id, active="Y", name="Pat Doe", **extra):
    return {"CT_ID": ct_id, "ContactNm": name, "IsActive": active, **extra}


def test_mixed_alias_group_imports_only_the_active_ct_id():
    people, markers, report, _company, _ = _contact_run(
        [
            _contact_row("1001", "Y", Email="pat@example.test", PhoneBusiness="215-555-0101"),
            _contact_row("1002", "N", Email="old@example.test", PhoneMobile="215-555-0102"),
        ]
    )
    assert len(people) == 1
    person = people[0]
    assert (person.email, person.phone, person.active) == ("pat@example.test", "215-555-0101", True)
    assert person.phone_line_ids == [], "an inactive alias contributes no number"
    assert markers.names() == ["legacy_erp_contact_1001"], "no XMLID for the inactive alias"
    assert report.counts["contacts"]["rejected"] == 0
    assert report.counts["contacts"]["skipped"] == 1
    assert report.unresolved == [], "an inactive CT_ID is omitted, not an open exception"


@pytest.mark.parametrize("flag", ["N", "", None, "X", "maybe"])
def test_a_group_with_no_explicitly_active_row_creates_no_person(flag):
    people, markers, report, company, _ = _contact_run(
        [
            _contact_row("2001", flag, Email="a@example.test", PhoneBusiness="215-555-0201"),
            _contact_row("2002", flag),
            _contact_row("2003", flag, name="215-555-0203", PhoneBusiness="215-555-0203"),
        ]
    )
    assert people == [] and markers.rows == []
    assert (company.email, company.phone) == (False, False), "an ineligible row writes no channel on the company"
    assert report.counts["contacts"] == {"created": 0, "updated": 0, "skipped": 3, "rejected": 0}
    assert report.unresolved == []


def test_contact_fields_land_on_the_documented_targets():
    people, markers, _report, _company, _ = _contact_run(
        [
            _contact_row(
                "3001",
                Email="pat@example.test; ops@scrapmanagement.com",
                PhoneBusiness="215-555-0301",
                PhoneMobile="215-555-0302",
                PhoneOther="215-555-0303",
                Notes="prefers mornings",
            ),
            _contact_row("3002", PhoneBusiness="215-555-0304", Notes="Fax: 215-555-0305"),
        ]
    )
    (person,) = people
    assert person.name == "Pat Doe" and person.parent_id == 1
    assert person.email == "pat@example.test", "internal staff mailboxes are dropped"
    assert person.phone == "215-555-0301"
    assert [(line.label, line.number) for line in person.phone_line_ids] == [
        ("mobile", "215-555-0302"),
        ("other", "215-555-0303"),
        ("fax", "215-555-0305"),
        ("other", "215-555-0304"),
    ]
    assert person.comment == "prefers mornings"
    assert markers.names() == ["legacy_erp_contact_3001", "legacy_erp_contact_3002"]


def test_a_distinct_active_alias_email_is_kept_as_evidence_and_replays_once():
    rows = [
        _contact_row("4001", Email="pat@example.test", Notes="ERP note"),
        _contact_row("4002", Email="PAT@example.test"),
        _contact_row("4003", Email="pat.doe@example.test; cc@scrapmanagement.com"),
        _contact_row("4004", Email="pat.doe@example.test"),
        _contact_row("4005", "N", Email="inactive@example.test"),
    ]
    people, _markers, report, _company, (service, index, partners) = _contact_run(rows)
    (person,) = people
    assert person.email == "pat@example.test", "the first ERP email stays the primary"
    from erp.comment_notes import _CommentBlocks

    def blocks(value):
        parser = _CommentBlocks()
        parser.feed(str(value))
        parser.close()
        parser.flush()
        return parser.blocks

    assert blocks(person.comment) == ["ERP note", "ERP contact 4003 email: pat.doe@example.test"]
    assert "inactive@example.test" not in person.comment and "scrapmanagement" not in person.comment
    # A CRM paragraph appended later survives, and a replay writes nothing new.
    person.comment = f"{person.comment}<p>CRM history</p>"
    stored, writes = person.comment, len(person.writes)
    from erp.report import ImportReport

    service._import_contacts(index, ImportReport(), {"C1": 1}, dry_run=False)
    assert person.comment == stored and len(person.writes) == writes
    assert blocks(person.comment) == ["ERP note", "ERP contact 4003 email: pat.doe@example.test", "CRM history"]
    assert len([p for p in partners.rows.values() if not p.is_company]) == 1


def test_an_earlier_inactive_alias_marker_is_removed_and_the_active_person_kept():
    people, markers, report, _company, _ = _contact_run(
        [_contact_row("5001", "N"), _contact_row("5002", "Y", Email="pat@example.test")],
        earlier={"Pat Doe": ["5001", "5002"]},
    )
    assert markers.names() == ["legacy_erp_contact_5002"], "the excluded CT_ID no longer resolves"
    (person,) = people
    assert person.active is True, "an active alias still names the person"
    assert report.unresolved == []
    assert report.counts["contacts"]["skipped"] == 1


def test_an_earlier_person_of_only_inactive_ct_ids_is_archived_not_deleted():
    people, markers, report, _company, (service, index, partners) = _contact_run(
        [_contact_row("6001", "N"), _contact_row("6002", "")],
        earlier={"Pat Doe": ["6001", "6002"], "Lee Roe": ["6003"]},
    )
    assert markers.names() == ["legacy_erp_contact_6003"], "a marker of a CT_ID not in the source is untouched"
    archived = {p.name: p.active for p in people}
    assert archived == {"Pat Doe": False, "Lee Roe": True}
    from erp.report import ImportReport

    replay = ImportReport()
    service._import_contacts(index, replay, {"C1": 1}, dry_run=False)
    assert markers.names() == ["legacy_erp_contact_6003"]
    assert len(partners.rows) == 3, "the replay creates and deletes nothing"
    assert replay.unresolved == []
    assert replay.counts["contacts"]["skipped"] == 2


def test_company_phone_and_email_are_filled_independently_preferring_the_primary():
    _people, _markers, _report, company, _ = _contact_run(
        [
            _contact_row("7001", Email="", PhoneBusiness="215-555-0701", name="Ann First"),
            _contact_row("7002", "N", PhoneBusiness="215-555-0702", name="Old Gone"),
            _contact_row("7003", Email="ap@example.test", PhoneBusiness="NULL", name="Bo Primary"),
            _contact_row("7004", Email="other@example.test", name="Cy Third"),
        ],
        roles={"7003": "Primary"},
    )
    assert company.email == "ap@example.test", "the primary contact's email wins"
    assert company.phone == "215-555-0701", "the primary has no real number, so the first active one supplies it"


def test_company_values_already_set_are_never_overwritten():
    _people, _markers, _report, company, _ = _contact_run(
        [_contact_row("7101", Email="pat@example.test", PhoneBusiness="215-555-0711")],
        existing_company={"email": "remit@example.test"},
    )
    assert company.email == "remit@example.test"
    assert company.phone == "215-555-0711", "only the missing phone is filled"


# ---------------------------------------------------------------------------
# Command dispatch (2026-11-07): one authoritative ERP execution path
# ---------------------------------------------------------------------------
SHELL_DRIVER = ROOT / "plasticos_partner_import" / "scripts" / "import_erp_shell.py"
MAKEFILE = ROOT / "Makefile"
RETIRED_ERP_PATHS = (
    "run_import.py",
    "run_transaction_import.py",
    "partner_import_service",
    "transaction_import_service",
    "transaction_import_wizard",
    "run_csv_import",
    "action_import",
)


def _import_erp_recipe() -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    return text.split("\nimport-erp:\n", 1)[1].split("\n\n", 1)[0]


def test_make_import_erp_pipes_only_the_canonical_shell_driver():
    recipe = _import_erp_recipe()
    assert recipe.count("< plasticos_partner_import/scripts/import_erp_shell.py") == 2, "both runtimes, one driver"
    for retired in RETIRED_ERP_PATHS:
        assert retired not in recipe, f"make import-erp must not reach {retired}"
    # The direct SQL source is required and a fixture root refused on both runtimes, before any runtime starts.
    assert recipe.count("$(erp_source_guard)") == 2
    assert recipe.count('ERP_PRODUCTION_PERMIT="$(call runtime_path,$(ERP_PRODUCTION_PERMIT))"') == 1
    assert recipe.count('ERP_PRODUCTION_PERMIT="$(ERP_PRODUCTION_PERMIT)"') == 1
    guard = MAKEFILE.read_text(encoding="utf-8").split("\nerp_source_guard = ", 1)[1].split("\n\n", 1)[0]
    assert "ERP_PAYLOAD_ROOT" in guard and "ERP_SQL_SERVER" in guard and "ERP_SQL_DATABASE" in guard


def test_shell_driver_reaches_the_native_service_and_its_active_commercial_extension(deal_source):
    source = SHELL_DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        f"{node.module}.{alias.name}"
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "odoo.addons.plasticos_partner_import.scripts.run_erp_import.run" in imported
    assert 'env["plasticos.erp.import"].run(' in RUNNER.read_text(encoding="utf-8")
    for retired in RETIRED_ERP_PATHS:
        assert retired not in source, f"the shell driver must not reach {retired}"
    # The historical filename is an active native-document extension of the same model, not a CSV importer.
    assert '_inherit = "plasticos.erp.import"' in deal_source
    init = (ROOT / "plasticos_transaction" / "models" / "__init__.py").read_text(encoding="utf-8")
    assert "from . import legacy_erp_import_service" in init

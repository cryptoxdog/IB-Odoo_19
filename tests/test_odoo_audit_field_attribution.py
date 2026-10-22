"""scripts/audit/odoo_audit.py view field attribution: valid fields pass, missing fields stay CRITICAL.

A focused owner: tests/test_audit_baseline_gate.py stubs the scanner to test the
baseline gate, so nothing else exercises how the scanner attributes a view
``<field>`` to a model. Each positive case has a negative twin that must still
fail, so a scanner that reports nothing cannot pass.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))

from odoo_audit import OdooAudit  # noqa: E402

BASE_MODELS = """
from .constants import IMPORTED_MODEL

PARTNER = "res.partner"
LINE = "sample.line"


class SampleOrder(models.Model):
    _name = "sample.order"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    partner_id = fields.Many2one(PARTNER, ondelete="restrict")
    other_id = fields.Many2one(IMPORTED_MODEL, ondelete="restrict")
    line_ids = fields.One2many(LINE, "order_id")
    tag_ids = fields.Many2many(comodel_name="sample.tag")
    amount = fields.Float()


class SampleLine(models.Model):
    _name = "sample.line"

    order_id = fields.Many2one("sample.order", ondelete="cascade")
    qty = fields.Float()


class SampleTag(models.Model):
    _name = "sample.tag"

    color = fields.Integer()


class SamplePrototype(models.Model):
    _name = "sample.prototype"
    _inherit = "sample.tag"

    extra = fields.Char()


class SampleWrapped(models.Model):
    _name = "sample.wrapped"
    _inherit = ["res.partner"]
"""

EXT_MODELS = """
class SampleOrderExtension(models.Model):
    _inherit = "sample.order"

    ext_score = fields.Integer()


class SampleLineExtension(models.Model):
    _inherit = ["sample.line"]

    ext_flag = fields.Boolean()
"""


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def _tree(tmp_path: Path) -> Path:
    _write(tmp_path, "sample_base/__manifest__.py", '{"name": "base", "depends": ["mail"]}')
    _write(tmp_path, "sample_base/models/order.py", BASE_MODELS)
    _write(tmp_path, "sample_ext/__manifest__.py", '{"name": "ext", "depends": ["sample_base"]}')
    _write(tmp_path, "sample_ext/models/order_ext.py", EXT_MODELS)
    _write(tmp_path, "sample_ui/__manifest__.py", '{"name": "ui", "depends": ["sample_ext"]}')
    _write(tmp_path, "sample_ui/models/__init__.py", "")
    _write(tmp_path, "sample_unrelated/__manifest__.py", '{"name": "unrelated", "depends": ["sample_base"]}')
    _write(tmp_path, "sample_unrelated/models/__init__.py", "")
    return tmp_path


def _view(record_id: str, model: str | None, arch: str, inherit: str | None = None) -> str:
    model_field = f'<field name="model">{model}</field>' if model else ""
    inherit_field = f'<field name="inherit_id" ref="{inherit}"/>' if inherit else ""
    return f"""
    <record id="{record_id}" model="ir.ui.view">
        <field name="name">{record_id}</field>
        {model_field}
        {inherit_field}
        <field name="arch" type="xml">{arch}</field>
    </record>"""


def _views(root: Path, module: str, *records: str) -> None:
    _write(root, f"{module}/views/views.xml", "<odoo>" + "".join(records) + "\n</odoo>\n")


def _findings(root: Path) -> list[dict]:
    audit = OdooAudit(root)
    with contextlib.redirect_stdout(io.StringIO()):
        errors = audit.run_all_checks()
    return [e for e in errors if e["type"] in {"FIELD_NOT_FOUND", "UNRESOLVED_VIEW_CONTEXT", "VIEW_PARSE_ERROR"}]


def _missing(root: Path) -> set[tuple[str, str]]:
    return {(e["model"], e["field"]) for e in _findings(root) if e["type"] == "FIELD_NOT_FOUND"}


def test_own_inherited_mixin_and_prototype_fields_resolve(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view(
            "order_form",
            "sample.order",
            """<form><field name="partner_id"/><field name="amount"/><field name="ext_score"/>
            <field name="message_ids"/><field name="activity_ids"/></form>""",
        ),
        _view("proto_form", "sample.prototype", '<form><field name="color"/><field name="extra"/></form>'),
    )
    assert _findings(root) == []


def test_a_truly_missing_field_is_critical(tmp_path: Path):
    root = _tree(tmp_path)
    _views(root, "sample_ui", _view("order_form", "sample.order", '<form><field name="no_such_field"/></form>'))
    findings = _findings(root)
    assert [(e["type"], e["severity"], e["model"], e["field"]) for e in findings] == [
        ("FIELD_NOT_FOUND", "CRITICAL", "sample.order", "no_such_field")
    ]
    assert findings[0]["message"] == "Field 'no_such_field' not defined on model 'sample.order'"


def test_extension_field_needs_the_extending_module_in_depends(tmp_path: Path):
    root = _tree(tmp_path)
    _views(root, "sample_unrelated", _view("order_form", "sample.order", '<form><field name="ext_score"/></form>'))
    assert _missing(root) == {("sample.order", "ext_score")}


def test_mixin_fields_need_the_mixin_in_inherit(tmp_path: Path):
    root = _tree(tmp_path)
    _views(root, "sample_ui", _view("line_form", "sample.line", '<form><field name="message_ids"/></form>'))
    assert _missing(root) == {("sample.line", "message_ids")}


def test_unresolved_framework_parent_does_not_excuse_a_field(tmp_path: Path):
    root = _tree(tmp_path)
    _views(root, "sample_ui", _view("wrapped_form", "sample.wrapped", '<form><field name="email"/></form>'))
    assert _missing(root) == {("sample.wrapped", "email")}


def test_one2many_list_subview_uses_the_comodel(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view(
            "order_form",
            "sample.order",
            """<form><field name="line_ids"><list><field name="qty"/><field name="ext_flag"/></list>
            <form><field name="order_id"/></form></field>
            <field name="tag_ids"><kanban><field name="color"/></kanban></field></form>""",
        ),
    )
    assert _findings(root) == []


def test_subview_does_not_borrow_parent_fields_and_misses_stay_critical(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view(
            "order_form",
            "sample.order",
            '<form><field name="line_ids"><list><field name="amount"/><field name="ghost"/></list></field></form>',
        ),
    )
    assert _missing(root) == {("sample.line", "amount"), ("sample.line", "ghost")}


def test_context_returns_to_the_parent_after_a_subview(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view(
            "order_form",
            "sample.order",
            '<form><field name="line_ids"><list><field name="qty"/></list></field><field name="qty"/></form>',
        ),
    )
    assert _missing(root) == {("sample.order", "qty")}


def test_xpath_into_a_subview_uses_the_comodel(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view("order_form", "sample.order", '<form><field name="line_ids"/></form>'),
        _view(
            "order_form_ext",
            None,
            """<data><xpath expr="//field[@name='line_ids']/list/field[@name='qty']" position="after">
            <field name="ext_flag"/><field name="ghost"/></xpath>
            <xpath expr="//field[@name='amount']" position="after"><field name="ext_score"/></xpath></data>""",
            inherit="sample_ui.order_form",
        ),
    )
    assert _missing(root) == {("sample.line", "ghost")}


def test_unresolvable_comodel_is_reported_not_charged_to_the_parent(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view(
            "order_form",
            "sample.order",
            """<form><field name="other_id"><form><field name="street"/></form></field>
            <field name="partner_id"><form><field name="street"/></form></field><field name="amount"/></form>""",
        ),
    )
    findings = _findings(root)
    # other_id's comodel is an imported constant: reported, its subview unchecked, nothing charged to the parent.
    # partner_id's comodel resolves to res.partner, a core model the check does not judge.
    assert [(e["type"], e["severity"], e["model"], e["field"]) for e in findings] == [
        ("UNRESOLVED_VIEW_CONTEXT", "HIGH", "sample.order", "other_id")
    ]


def test_non_view_records_are_not_view_fields_and_do_not_leak_context(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view("order_form", "sample.order", '<form><field name="amount"/></form>'),
        """
    <record id="order_action" model="ir.actions.act_window">
        <field name="name">Orders</field>
        <field name="res_model">sample.order</field>
        <field name="target">current</field>
        <field name="res_id" eval="False"/>
    </record>
    <record id="order_cron" model="ir.cron">
        <field name="model_id" ref="model_sample_order"/>
        <field name="state">code</field>
        <field name="code">model.run()</field>
        <field name="interval_number">1</field>
    </record>""",
        _view("tag_form", "sample.tag", '<form><field name="color"/><field name="code"/></form>'),
    )
    assert _missing(root) == {("sample.tag", "code")}


def test_an_unparseable_view_file_is_reported_not_skipped(tmp_path: Path):
    root = _tree(tmp_path)
    _write(root, "sample_ui/views/broken.xml", "<odoo><record id='x' model='ir.ui.view'></odoo>")
    findings = _findings(root)
    assert [(e["type"], e["severity"]) for e in findings] == [("VIEW_PARSE_ERROR", "HIGH")]
    assert findings[0]["file"].endswith("sample_ui/views/broken.xml")


def test_core_models_without_a_repo_definition_are_not_checked(tmp_path: Path):
    root = _tree(tmp_path)
    _views(root, "sample_ui", _view("partner_form", "res.partner", '<form><field name="anything"/></form>'))
    assert _findings(root) == []


def test_repository_has_no_unbaselined_findings(monkeypatch):
    """The real tree, scanned the way CI scans it (``odoo_audit.py .``), adds no unlogged CRITICAL/HIGH."""
    from baseline_utils import compute_fingerprint

    monkeypatch.chdir(ROOT)
    with contextlib.redirect_stdout(io.StringIO()):
        errors = OdooAudit(".").run_all_checks()
    baseline = json.loads((ROOT / "ci" / "baselines" / "odoo_audit_baseline.json").read_text(encoding="utf-8"))
    logged = {entry["fingerprint"] for entry in baseline["entries"]}
    new = [e for e in errors if e["severity"] in {"CRITICAL", "HIGH"} and compute_fingerprint(e) not in logged]
    assert new == []


def test_subview_inserted_by_xpath_into_a_field_uses_the_comodel(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view("order_form", "sample.order", '<form><field name="line_ids"/></form>'),
        _view(
            "order_form_ext",
            None,
            """<data><xpath expr="//field[@name='line_ids']" position="inside">
            <list><field name="qty"/><field name="ghost"/></list></xpath>
            <xpath expr="//field[@name='amount']" position="after"><field name="ext_score"/></xpath></data>""",
            inherit="sample_ui.order_form",
        ),
    )
    assert _missing(root) == {("sample.line", "ghost")}


def test_relative_root_resolves_manifest_depends(tmp_path: Path, monkeypatch):
    _tree(tmp_path / "checkout")
    _views(
        tmp_path / "checkout",
        "sample_ui",
        _view("order_form", "sample.order", '<form><field name="ext_score"/></form>'),
    )
    _views(
        tmp_path / "checkout",
        "sample_unrelated",
        _view("order_form_2", "sample.order", '<form><field name="ext_score"/></form>'),
    )
    monkeypatch.chdir(tmp_path)
    assert _missing(Path("checkout")) == {("sample.order", "ext_score")}
    assert {e["file"] for e in _findings(Path("checkout"))} == {"checkout/sample_unrelated/views/views.xml"}


def test_xpath_axes_and_class_text_are_not_subview_steps(tmp_path: Path):
    root = _tree(tmp_path)
    _views(
        root,
        "sample_ui",
        _view("order_form", "sample.order", '<form><field name="partner_id"/><field name="amount"/></form>'),
        _view(
            "order_form_ext",
            None,
            """<data>
            <xpath expr="//field[@name='partner_id']/following-sibling::div[hasclass('form-group')]" position="inside">
                <field name="bogus_class_text"/></xpath>
            <xpath expr="//field[@name='partner_id']/ancestor::form" position="inside">
                <field name="bogus_ancestor"/></xpath>
            <xpath expr="//field[@name='amount']/parent::form" position="inside">
                <field name="bogus_parent"/></xpath>
            <xpath expr="//field[@name='line_ids']/.." position="inside">
                <list><field name="bogus_not_inside_the_field"/></list></xpath>
            </data>""",
            inherit="sample_ui.order_form",
        ),
    )
    assert _missing(root) == {
        ("sample.order", "bogus_class_text"),
        ("sample.order", "bogus_ancestor"),
        ("sample.order", "bogus_parent"),
        ("sample.order", "bogus_not_inside_the_field"),
    }

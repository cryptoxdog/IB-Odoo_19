"""Field declarations that kept the Odoo.sh Staging update log at WARNING.

Odoo 19 sources:
- ``odoo/orm/fields.py`` (``Field.resolve_depends``, line 830): a field whose compute
  depends on itself through a relation and is not declared ``recursive=True`` is
  flagged and logs ``UserWarning: Field ... should be declared with recursive=True``.
- ``odoo/addons/base/models/ir_model.py`` (``_reflect_fields``, line 1236): two
  fields of one model with the same ``string`` log ``Two fields ... have the same label``.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTNER_PY = ROOT / "plasticos_facility_profile" / "models" / "res_partner.py"
CRM_WEB_LEAD_PY = ROOT / "plasticos_crm_bridge" / "models" / "web_lead.py"
WEB_LEAD_PY = ROOT / "plasticos_web_leads" / "models" / "web_lead.py"


def _field_kwargs(path: Path, field_name: str) -> dict[str, object]:
    """Keyword arguments of the single class-level ``field_name = fields.X(...)``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        for item in cls.body:
            if (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and item.targets[0].id == field_name
                and isinstance(item.value, ast.Call)
            ):
                found.append(item.value)
    assert len(found) == 1, f"{field_name} declared {len(found)} times in {path.name}"
    return {kw.arg: ast.literal_eval(kw.value) for kw in found[0].keywords if isinstance(kw.value, ast.Constant)}


def test_partner_user_id_override_is_declared_recursive():
    kwargs = _field_kwargs(PARTNER_PY, "user_id")
    assert kwargs.get("recursive") is True
    # Only the flag is added; base keeps compute, store, readonly and precompute.
    assert set(kwargs) == {"recursive"}


def test_linked_person_labels_do_not_collide_with_email_and_mobile():
    email = _field_kwargs(PARTNER_PY, "linked_person_email")["string"]
    mobile = _field_kwargs(PARTNER_PY, "linked_person_mobile")["string"]
    own_mobile = _field_kwargs(PARTNER_PY, "mobile")["string"]
    assert email == "Linked Person Email"
    assert mobile == "Linked Person Mobile"
    # res.partner.email is labelled "Email" in base.
    assert len({email, mobile, own_mobile, "Email"}) == 4


def test_opportunity_salesperson_label_differs_from_queue_assignee():
    opportunity = _field_kwargs(CRM_WEB_LEAD_PY, "opportunity_user_id")["string"]
    assignee = _field_kwargs(WEB_LEAD_PY, "assigned_user_id")["string"]
    assert assignee == "Assigned To"
    assert opportunity == "Opportunity Salesperson"
    assert opportunity != assignee

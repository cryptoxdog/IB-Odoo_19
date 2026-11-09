"""Contact list, location layout, and parent salesperson stay on their owners."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTNER_PY = ROOT / "plasticos_facility_profile" / "models" / "res_partner.py"
PARTNER_UX = ROOT / "plasticos_facility_profile" / "views" / "partner_ux.xml"
FACILITY_VIEWS = ROOT / "plasticos_facility_profile" / "views" / "facility_profile_views.xml"
MATERIAL_UX = ROOT / "plasticos_material_profile" / "views" / "partner_material_ux.xml"
IMPORTER = ROOT / "plasticos_partner_import" / "models" / "erp_import_service.py"


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    functions = [
        item for cls in matches for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == name
    ]
    assert len(functions) == 1, name
    return functions[0]


def test_contacts_list_shows_first_and_last_name_after_name():
    text = PARTNER_UX.read_text(encoding="utf-8")
    name_at = text.index("field[@name='complete_name']")
    first_at = text.index('name="first_name" optional="show"', name_at)
    last_at = text.index('name="last_name" optional="show"', first_at)
    assert name_at < first_at < last_at
    assert 'name="first_name" invisible="is_company"' in text
    assert 'name="last_name" invisible="is_company"' in text


def test_material_profile_sits_above_the_notebook_at_priority_10():
    text = MATERIAL_UX.read_text(encoding="utf-8")
    assert '<field name="priority">10</field>' in text
    assert "<page" not in text
    assert 'position="before"' in text
    assert "notebook[page[@name='internal_notes']]" in text
    assert 'string="Material Profile"' in text


def test_locations_list_is_full_width_and_has_the_address_columns():
    text = FACILITY_VIEWS.read_text(encoding="utf-8")
    assert '<group string="Locations"' not in text
    assert '<separator string="Locations"' in text
    locations_at = text.index('name="location_child_ids"')
    list_end = text.index("</list>", locations_at)
    columns = text[locations_at:list_end]
    for column in (
        'name="name"',
        'string="Address Type"',
        'name="street"',
        'name="city"',
        'name="state_id"',
        'name="zip"',
        'name="country_id"',
        'name="phone"',
        'name="linked_person_email" string="Email"',
        'name="user_id" string="Salesperson"',
    ):
        assert column in columns
    assert text.count('string="Payment Terms"') == 2
    assert "Supplier Payment Terms" not in text


def _depends_args(path: Path, name: str) -> list[str]:
    function = _function(path, name)
    depends = [
        decorator
        for decorator in function.decorator_list
        if isinstance(decorator, ast.Call) and getattr(decorator.func, "attr", None) == "depends"
    ]
    assert len(depends) == 1
    return [arg.value for arg in depends[0].args if isinstance(arg, ast.Constant)]


def test_salesperson_compute_copies_the_parent_and_does_not_clear_an_empty_one():
    text = PARTNER_PY.read_text(encoding="utf-8")
    depends = _depends_args(PARTNER_PY, "_compute_user_id")
    assert "parent_id.user_id" in depends
    assert "parent_id.parent_id.user_id" in depends
    source = ast.get_source_segment(text, _function(PARTNER_PY, "_compute_user_id"))
    assert source is not None
    assert "partner.user_id = source" in source
    assert "partner.user_id = False" not in source
    helper = ast.get_source_segment(text, _function(PARTNER_PY, "_salesperson_from_parent"))
    assert helper is not None
    assert "parent.user_id" in helper
    assert "parent.parent_id.user_id" in helper


def test_location_email_and_mobile_are_computed_and_not_written_by_the_importer():
    partner = PARTNER_PY.read_text(encoding="utf-8")
    assert "def _compute_linked_person_channels" in partner
    assert "linked_person_email" in partner
    assert "linked_person_mobile" in partner
    importer = IMPORTER.read_text(encoding="utf-8")
    assert "linked_person_email" not in importer
    assert "linked_person_mobile" not in importer

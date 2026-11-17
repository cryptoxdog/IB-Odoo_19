"""Contact list, location layout, and parent salesperson stay on their owners."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTNER_PY = ROOT / "plasticos_facility_profile" / "models" / "res_partner.py"
PARTNER_UX = ROOT / "plasticos_facility_profile" / "views" / "partner_ux.xml"
FACILITY_VIEWS = ROOT / "plasticos_facility_profile" / "views" / "facility_profile_views.xml"
MATERIAL_UX = ROOT / "plasticos_material_profile" / "views" / "partner_material_ux.xml"
MATERIAL_MANIFEST = ROOT / "plasticos_material_profile" / "__manifest__.py"
FACILITY_MANIFEST = ROOT / "plasticos_facility_profile" / "__manifest__.py"
ENRICHMENT_VIEWS = ROOT / "plasticos_enrichment" / "views" / "res_partner_enrichment.xml"
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
    # C1 D1 (ADR-131): a site is neither a person nor a company, so the name parts show for people only.
    assert 'name="first_name" invisible="company_type != \'person\'"' in text
    assert 'name="last_name" invisible="company_type != \'person\'"' in text


def test_material_profile_sits_above_the_notebook_at_priority_10():
    text = MATERIAL_UX.read_text(encoding="utf-8")
    assert '<field name="priority">10</field>' in text
    assert "<page" not in text
    assert 'position="before"' in text
    assert "notebook[page[@name='internal_notes']]" in text
    assert 'string="Material Profile"' in text
    assert 'delete="0"' in text
    assert 'name="action_remove_profile"' in text
    assert 'title="Remove material profile"' in text


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
    salesperson = columns.index('name="user_id" string="Salesperson"')
    trash = columns.index('name="action_remove_location"')
    assert salesperson < trash
    assert 'icon="fa-trash"' in columns
    assert 'title="Remove location"' in columns
    assert text.count('string="Payment Terms"') == 1
    assert "Supplier Payment Terms" not in text
    company_card = text.split("field[@name='vat']", 1)[1].split("</xpath>", 1)[0]
    assert 'name="lead_source_id"' in company_card
    assert 'name="category_id"' in company_card
    assert company_card.index('name="lead_source_id"') < company_card.index('name="category_id"')
    assert company_card.index('name="category_id"') < company_card.index('string="Salesperson"')
    assert "Payment Terms" not in company_card
    private = (ROOT / "plasticos_security_base" / "views" / "res_partner_views.xml").read_text(encoding="utf-8")
    private_field = private.split('name="is_private"', 1)[1].split("/>", 1)[0]
    assert 'readonly="1"' in private_field


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


def test_vendor_term_compute_copies_the_parent_and_does_not_clear_an_empty_one():
    text = PARTNER_PY.read_text(encoding="utf-8")
    depends = _depends_args(PARTNER_PY, "_compute_supplier_payment_term_id")
    assert "parent_id" in depends
    assert "parent_id.property_supplier_payment_term_id" in depends
    assert "parent_id.parent_id.property_supplier_payment_term_id" in depends
    source = ast.get_source_segment(text, _function(PARTNER_PY, "_compute_supplier_payment_term_id"))
    assert source is not None
    assert "partner.property_supplier_payment_term_id = source" in source
    assert "partner.property_supplier_payment_term_id = False" not in source
    helper = ast.get_source_segment(text, _function(PARTNER_PY, "_supplier_payment_term_from_parent"))
    assert helper is not None
    assert "parent.property_supplier_payment_term_id" in helper
    assert "parent.parent_id.property_supplier_payment_term_id" in helper


def test_form_bale_is_inactive():
    text = (ROOT / "plasticos_material_profile" / "data" / "material_form_data.xml").read_text(encoding="utf-8")
    record = text.split('id="form_bale"', 1)[1].split("</record>", 1)[0]
    assert '<field name="active" eval="False"/>' in record
    migrate = (ROOT / "plasticos_material_profile" / "migrations" / "19.0.5.11.14" / "post-migrate.py").read_text(
        encoding="utf-8"
    )
    assert "env.ref(FORM_BALE" in migrate
    assert "plasticos_material_profile.form_bale" in migrate
    assert "plasticos_material_profile.packaging_bales" in migrate


def test_partner_material_list_shows_packaging_type():
    text = MATERIAL_UX.read_text(encoding="utf-8")
    material_list = text.split("<list", 1)[1].split("</list>", 1)[0]
    assert 'name="packaging_type_id" string="Packaging Type"' in material_list
    assert "contamination_percent" not in material_list


def test_open_full_profile_saves_the_material_line():
    text = MATERIAL_UX.read_text(encoding="utf-8")
    assert 'open_form_view="1"' in text
    assert 'class="o_material_profile_lines"' in text
    assert "action_open_profile_form" not in text
    manifest = MATERIAL_MANIFEST.read_text(encoding="utf-8")
    assert "plasticos_material_profile/static/src/material_profile_lines.css" in manifest


def test_open_full_profile_saves_the_facility_line():
    text = FACILITY_VIEWS.read_text(encoding="utf-8")
    facility_field = text.split('<field name="facility_profile_ids"', 1)[1].split("</field>", 1)[0]
    assert 'open_form_view="1"' in facility_field
    assert 'class="o_material_profile_lines"' in facility_field
    assert "action_open_profile_form" not in facility_field
    assert 'delete="0"' in facility_field
    assert 'name="action_remove_profile"' in facility_field
    assert 'title="Remove facility profile"' in facility_field


def test_facility_profile_is_a_section_above_locations():
    text = FACILITY_VIEWS.read_text(encoding="utf-8")
    assert '<page string="Facility Profile"' not in text
    assert text.index('string="Facility Profile"') < text.index('string="Locations"')
    section = text[text.index('string="Facility Profile"') : text.index('name="facility_profile_ids"')]
    assert "<group" not in section
    assert (
        'invisible="not is_facility"'
        in text[text.index('string="Facility Profile"') : text.index('string="Locations"')]
    )
    partner_ux = PARTNER_UX.read_text(encoding="utf-8")
    assert "page[@name='facility_profile']" not in partner_ux


def test_people_list_is_full_width():
    text = FACILITY_VIEWS.read_text(encoding="utf-8")
    assert '<separator string="People"' in text
    assert '<group string="People"' not in text


def test_location_save_stays_open_for_a_company_with_a_parent():
    script = (ROOT / "plasticos_facility_profile" / "static" / "src" / "location_dialog_save.js").read_text(
        encoding="utf-8"
    )
    assert 'record.resModel === "res.partner"' in script
    assert "record.data.is_company" in script
    assert "record.data.parent_id" in script
    assert "this.env.inDialog" in script
    assert "saveButtonClicked({})" in script
    assert "saveButtonClicked(params)" in script
    manifest = FACILITY_MANIFEST.read_text(encoding="utf-8")
    assert "plasticos_facility_profile/static/src/location_dialog_save.js" in manifest


def test_enrichment_sources_and_runs_are_full_width():
    text = ENRICHMENT_VIEWS.read_text(encoding="utf-8")
    assert '<separator string="Sources"' in text
    assert '<separator string="Runs"' in text
    assert '<group string="Sources"' not in text
    assert '<group string="Runs"' not in text


def test_location_email_and_mobile_are_computed_and_not_written_by_the_importer():
    partner = PARTNER_PY.read_text(encoding="utf-8")
    assert "def _compute_linked_person_channels" in partner
    assert "linked_person_email" in partner
    assert "linked_person_mobile" in partner
    importer = IMPORTER.read_text(encoding="utf-8")
    assert "linked_person_email" not in importer
    assert "linked_person_mobile" not in importer

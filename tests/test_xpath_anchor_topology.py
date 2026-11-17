"""Named XPath anchors are the notebook policy. Positional notebook indexes stay visible."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parents[1]
CI = ROOT / "ci"
sys.path.insert(0, str(CI))
SPEC = importlib.util.spec_from_file_location("check_xpath_stability", CI / "check_xpath_stability.py")
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)

NAMED_NOTEBOOKS = {
    "plasticos_transaction/views/transaction_views.xml": "transaction_pages",
    "plasticos_material_profile/views/material_profile_views.xml": "material_profile_pages",
    "plasticos_facility_profile/views/facility_profile_views.xml": "facility_profile_pages",
    "plasticos_intake/views/intake_views.xml": "intake_pages",
}


def test_notebook_guidance_names_an_anchor():
    for _pattern, issue_type, _severity, _message, fix in checker.RISKY_PATTERNS:
        if issue_type in {"UNSCOPED_NOTEBOOK", "UNSCOPED_SHEET_NOTEBOOK"}:
            assert "notebook[1]" not in fix
            assert "[1]" not in fix
            assert "@name" in fix
    assert "notebook[1]" not in checker.SAFE_PATTERNS[0]
    assert all("notebook[1]" not in pattern for pattern in checker.SAFE_PATTERNS)


def test_positional_notebook_is_a_finding_and_class_guidance_stays():
    findings = checker.check_xpath("//notebook[1]", "view.xml", "sample")
    assert [item.issue_type for item in findings] == ["POSITIONAL_NOTEBOOK"]
    assert "notebook[1]" not in findings[0].fix_suggestion
    sheet = checker.check_xpath("//sheet/notebook[1]", "view.xml", "sample")
    assert sheet[0].issue_type == "POSITIONAL_NOTEBOOK"
    named_index = checker.check_xpath("//notebook[@name='pages'][1]", "view.xml", "sample")
    assert named_index[0].issue_type == "POSITIONAL_NOTEBOOK"
    class_fix = next(fix for _p, issue, _s, _m, fix in checker.RISKY_PATTERNS if issue == "CLASS_BASED_ANCHOR")
    assert "[1]" not in class_fix
    assert "@name" in class_fix


def test_class_anchor_stays_a_finding_with_or_without_an_index():
    for xpath in (
        "//div[@class='oe_title']",
        "//div[@class='oe_title'][1]",
        '//div[@class="oe_title"][1]',
        "//sheet//div[@class='oe_title'][1]/h1",
        "//div[@class='oe_title'][1]//group[@name='details']",
        "//div[@class='oe_title']//group[@name='details']",
        "//div[@class='oe_title'][1]//page[@name='pages']",
        "//div[@class='oe_title']//field[@name='name']//list/field[@name='x']",
        "//div[@name='header']//div[@class='oe_title'][1]",
    ):
        findings = checker.check_xpath(xpath, "view.xml", "sample")
        assert [(item.issue_type, item.severity) for item in findings] == [("CLASS_BASED_ANCHOR", "HIGH")], xpath
        assert "[1]" not in findings[0].fix_suggestion
    assert all("oe_title" not in pattern for pattern in checker.SAFE_PATTERNS)


def test_named_anchor_replacing_a_class_anchor_is_accepted():
    for xpath in ("//div[@name='title']", "//field[@name='name']", "//div[@name='button_box']/button[@name='x']"):
        findings = checker.check_xpath(xpath, "view.xml", "sample")
        assert "CLASS_BASED_ANCHOR" not in [item.issue_type for item in findings], xpath


def test_positional_index_after_any_notebook_predicate_is_a_finding():
    for xpath in (
        "//notebook[page[@name='internal_notes']][1]",
        "//notebook[page[@name='a'][@string='b']][2]",
        "//notebook[@name='pages'][page[@name='x']][1]",
        "//notebook[1][@name='pages']",
        "//notebook[ 1 ]",
        "//notebook[last()]",
        "//notebook[position()=2]",
        "//sheet/notebook[page[@name=\"x\"]][1]/page[@name='y']",
        "//form/child::notebook[3]",
        "//page[@name='x'][ancestor::notebook[1]]",
        "//notebook [1]",
        "//notebook[@name='pages'] [1]",
        "//notebook\t[last()]",
    ):
        findings = checker.check_xpath(xpath, "view.xml", "sample")
        assert [item.issue_type for item in findings] == ["POSITIONAL_NOTEBOOK"], xpath


def test_indexes_owned_by_other_nodes_are_not_notebook_findings():
    for xpath in (
        "//notebook[page[1]]",
        "//notebook[page[@name='x']/group[1]]",
        "//notebook[@name='pages']/page[2]",
        "//notebook//group[1]",
        "//notebook[@name='a[1]']",
        "//notebook_extra[1]",
        "//field[@name='notebook'][1]",
        "//page[@notebook][1]",
        "//notebook [@name='pages'] /page[1]",
    ):
        findings = checker.check_xpath(xpath, "view.xml", "sample")
        assert "POSITIONAL_NOTEBOOK" not in [item.issue_type for item in findings], xpath


def test_named_notebook_and_named_page_are_not_findings():
    assert checker.check_xpath("//notebook[@name='intake_pages']", "view.xml", "sample") == []
    assert checker.check_xpath("//notebook[page[@name='internal_notes']]", "view.xml", "sample") == []
    assert checker.check_xpath("//notebook//field[@name='capability_type_id']", "view.xml", "sample") == []


def test_unscoped_list_field_scopes_to_the_named_field(tmp_path: Path):
    view = tmp_path / "partner_list.xml"
    view.write_text(
        """<odoo><record id="partner_list" model="ir.ui.view">
        <field name="inherit_id" ref="base.view_partner_tree"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='country_id']" position="before"/>
        </field>
        </record></odoo>"""
    )
    findings = checker.analyze_xml_file(view)
    assert [item.issue_type for item in findings] == ["UNSCOPED_LIST_FIELD"]
    assert findings[0].fix_suggestion == "Use //list/field[@name='country_id']"
    scoped = view.read_text().replace("//field[@name='country_id']", "//list/field[@name='country_id']")
    view.write_text(scoped)
    assert checker.analyze_xml_file(view) == []


def test_repo_medium_notebook_findings_are_named():
    findings = checker.scan_directory(ROOT)
    medium = [item for item in findings if item.severity == "MEDIUM"]
    assert medium == []
    assert [item for item in findings if item.severity in {"CRITICAL", "HIGH"}] == []
    for rel, name in NAMED_NOTEBOOKS.items():
        root = ET.parse(ROOT / rel).getroot()
        assert any(node.attrib.get("name") == name for node in root.iter("notebook"))
    for path in (ROOT / "plasticos_facility_profile/views").glob("*.xml"):
        text = path.read_text()
        assert "notebook[1]" not in text
        assert "[1]" not in text


def test_safe_patterns_still_exempt_notebook_rules_but_not_class_anchors():
    # A named page anchors a sheet notebook; that exemption is unchanged.
    assert checker.check_xpath("//sheet/notebook//page[@name='pages']", "view.xml", "sample") == []
    assert [f.issue_type for f in checker.check_xpath("//sheet/notebook", "view.xml", "sample")] == [
        "UNSCOPED_SHEET_NOTEBOOK"
    ]
    assert checker.INDEPENDENT_OF_SAFE_PATTERNS == {"CLASS_BASED_ANCHOR"}

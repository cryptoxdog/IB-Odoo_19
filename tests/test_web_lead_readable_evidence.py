"""The web-lead form shows labeled evidence and keeps the stored JSON fields."""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plasticos_web_leads"
VIEW = MODULE / "views" / "web_lead_views.xml"
STORED_JSON_FIELDS = (
    "ai_analysis",
    "decision_reasons",
    "ai_normalized",
    "ai_vision_results",
    "image_urls",
    "raw_payload",
)


def _form_sheet() -> ET.Element:
    tree = ET.parse(VIEW)
    for record in tree.findall("record"):
        if record.get("id") == "view_web_lead_form":
            sheet = record.find("field[@name='arch']/form/sheet")
            assert sheet is not None
            return sheet
    raise AssertionError("view_web_lead_form is missing")


def _page(sheet: ET.Element, name: str) -> ET.Element:
    page = sheet.find(f"notebook/page[@name='{name}']")
    assert page is not None
    return page


def test_sheet_sections_are_full_width_in_order():
    sheet = _form_sheet()
    labels = [group.get("string") for group in list(sheet) if group.tag == "group"]
    assert labels == ["Contact", "Material", "Classification", "Links"]
    links = next(group for group in list(sheet) if group.tag == "group" and group.get("string") == "Links")
    assert links.get("name") == "links"
    assert sheet.find("group/group[@string='Classification']") is None
    assert sheet.find("group/group[@string='Links']") is None
    quantity = sheet.find(".//field[@name='quantity_text']")
    assert quantity is not None
    assert quantity.get("string") == "Quantity"


def test_first_three_tabs_use_lead_evidence_modes():
    sheet = _form_sheet()
    analysis = _page(sheet, "ai_analysis_page").find("field[@name='ai_analysis']")
    triage = _page(sheet, "ai_triage_page").find("field[@name='ai_normalized']")
    payload = _page(sheet, "raw_payload_page").find("field[@name='raw_payload']")
    assert analysis.get("widget") == "lead_evidence"
    assert triage.get("widget") == "lead_evidence"
    assert payload.get("widget") == "lead_evidence"
    assert "analysis" in analysis.get("options")
    assert "triage" in triage.get("options")
    assert "payload" in payload.get("options")
    reasons = _page(sheet, "ai_analysis_page").find("field[@name='decision_reasons']")
    assert reasons.get("invisible") == "1"
    assert reasons.get("widget") is None
    triage_page = _page(sheet, "ai_triage_page")
    assert triage_page.find("field[@name='ai_vision_results']").get("invisible") == "1"
    assert triage_page.find("field[@name='image_urls']").get("invisible") == "1"
    log = triage_page.find(".//field[@name='triage_log']")
    assert log.get("widget") == "text"
    assert log.get("class") == "o_lead_triage_log"
    for field_name in STORED_JSON_FIELDS:
        assert sheet.find(f".//field[@name='{field_name}']") is not None


def test_provider_audit_stays_machine_readable():
    sheet = _form_sheet()
    audit = _page(sheet, "provider_audit_page")
    assert audit.find(".//field[@name='canonical_payload']").get("widget") == "json"
    assert audit.find(".//field[@name='evidence_bundle']").get("widget") == "json"
    for page_name in ("ai_analysis_page", "ai_triage_page", "raw_payload_page"):
        assert _page(sheet, page_name).find(".//field[@widget='json']") is None


def test_technical_view_redacts_secrets_and_starts_closed():
    formatter = (MODULE / "static/src/lead_evidence/format.js").read_text(encoding="utf-8")
    template = (MODULE / "static/src/lead_evidence/lead_evidence.xml").read_text(encoding="utf-8")
    component = (MODULE / "static/src/lead_evidence/lead_evidence.js").read_text(encoding="utf-8")
    manifest = (MODULE / "__manifest__.py").read_text(encoding="utf-8")
    assert "[redacted]" in formatter
    for key in ("source_url", "api_key", "adminlink", "token", "useragent", "ipaddress"):
        assert key in formatter
    assert "t-att-href" not in template
    assert "t-out" not in template
    assert "t-esc" in template
    assert "technical: false" in component
    assert "Show technical data" in component
    assert '"version": "19.0.2.8.13"' in manifest
    for asset in (
        "lead_evidence/format.js",
        "lead_evidence/lead_evidence.js",
        "lead_evidence/lead_evidence.xml",
        "lead_evidence/lead_evidence.scss",
    ):
        assert asset in manifest

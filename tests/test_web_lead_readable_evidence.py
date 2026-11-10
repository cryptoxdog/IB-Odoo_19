"""The web-lead form shows labeled evidence and keeps the stored JSON fields."""

from __future__ import annotations

import ast
from pathlib import Path

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
SECTION_LABELS = ("Contact", "Material", "Classification", "Links")


def _form_view() -> str:
    text = VIEW.read_text(encoding="utf-8")
    start = text.index('<record id="view_web_lead_form"')
    end = text.index('<record id="view_web_lead_kanban"')
    return text[start:end]


def _tag_block(source: str, tag: str, attr: str, value: str) -> str:
    """Return one opening tag and its body. The view is repo source, read as text."""
    marker = f'{attr}="{value}"'
    open_at = source.index(marker)
    start = source.rfind(f"<{tag}", 0, open_at)
    if start < 0:
        raise AssertionError(f"missing <{tag}> for {marker}")
    closer = f"</{tag}>"
    depth = 0
    cursor = start
    while cursor < len(source):
        next_open = source.find(f"<{tag}", cursor)
        next_close = source.find(closer, cursor)
        if next_close < 0:
            raise AssertionError(f"unclosed <{tag}> for {marker}")
        if next_open >= 0 and next_open < next_close:
            depth += 1
            cursor = next_open + len(tag) + 1
            continue
        depth -= 1
        cursor = next_close + len(closer)
        if depth == 0:
            return source[start:cursor]
    raise AssertionError(f"unclosed <{tag}> for {marker}")


def _page(form: str, name: str) -> str:
    return _tag_block(form, "page", "name", name)


def _field_tag(block: str, name: str) -> str:
    marker = f'name="{name}"'
    open_at = block.index(marker)
    start = block.rfind("<field", 0, open_at)
    end = block.index(">", open_at) + 1
    return block[start:end]


def _attr(tag: str, name: str) -> str | None:
    marker = f'{name}="'
    if marker not in tag:
        return None
    start = tag.index(marker) + len(marker)
    return tag[start : tag.index('"', start)]


def test_sheet_sections_are_full_width_in_order():
    form = _form_view()
    sheet = _tag_block(form, "sheet", "class", "oe_button_box").split("<notebook", 1)[0]
    positions = [sheet.index(f'string="{label}"') for label in SECTION_LABELS]
    assert positions == sorted(positions)
    indents = []
    for label in SECTION_LABELS:
        line = next(row for row in sheet.splitlines() if f'string="{label}"' in row)
        indents.append(len(line) - len(line.lstrip(" ")))
    assert indents == [indents[0]] * len(SECTION_LABELS)
    links = next(row for row in sheet.splitlines() if 'string="Links"' in row)
    assert 'name="links"' in links
    quantity = _field_tag(sheet, "quantity_text")
    assert _attr(quantity, "string") == "Quantity"


def test_first_three_tabs_use_lead_evidence_modes():
    form = _form_view()
    analysis = _field_tag(_page(form, "ai_analysis_page"), "ai_analysis")
    triage = _field_tag(_page(form, "ai_triage_page"), "ai_normalized")
    payload = _field_tag(_page(form, "raw_payload_page"), "raw_payload")
    assert _attr(analysis, "widget") == "lead_evidence"
    assert _attr(triage, "widget") == "lead_evidence"
    assert _attr(payload, "widget") == "lead_evidence"
    assert "analysis" in (_attr(analysis, "options") or "")
    assert "triage" in (_attr(triage, "options") or "")
    assert "payload" in (_attr(payload, "options") or "")
    reasons = _field_tag(_page(form, "ai_analysis_page"), "decision_reasons")
    assert _attr(reasons, "invisible") == "1"
    assert _attr(reasons, "widget") is None
    triage_page = _page(form, "ai_triage_page")
    assert _attr(_field_tag(triage_page, "ai_vision_results"), "invisible") == "1"
    assert _attr(_field_tag(triage_page, "image_urls"), "invisible") == "1"
    log = _field_tag(triage_page, "triage_log")
    assert _attr(log, "widget") == "text"
    assert _attr(log, "class") == "o_lead_triage_log"
    for field_name in STORED_JSON_FIELDS:
        assert f'name="{field_name}"' in form


def test_provider_audit_stays_machine_readable():
    form = _form_view()
    audit = _page(form, "provider_audit_page")
    assert _attr(_field_tag(audit, "canonical_payload"), "widget") == "json"
    assert _attr(_field_tag(audit, "evidence_bundle"), "widget") == "json"
    for page_name in ("ai_analysis_page", "ai_triage_page", "raw_payload_page"):
        assert 'widget="json"' not in _page(form, page_name)


def test_technical_view_redacts_secrets_and_starts_closed():
    formatter = (MODULE / "static/src/lead_evidence/format.js").read_text(encoding="utf-8")
    template = (MODULE / "static/src/lead_evidence/lead_evidence.xml").read_text(encoding="utf-8")
    component = (MODULE / "static/src/lead_evidence/lead_evidence.js").read_text(encoding="utf-8")
    manifest = (MODULE / "__manifest__.py").read_text(encoding="utf-8")
    assert "[redacted]" in formatter
    for key in ("source_url", "api_key", "adminlink", "token", "useragent", "ipaddress"):
        assert key in formatter
    assert "t-att-href" not in template
    assert "t-esc" not in template
    assert "t-out" in template
    assert "technical: false" in component
    assert "Show technical data" in component
    # The evidence widget shipped in 19.0.2.8.13. Later stacked changes bump the version again, so the
    # guard is "at least", not an exact string that every later bump breaks.
    version = ast.literal_eval(manifest)["version"]
    assert tuple(int(part) for part in version.split(".")) >= (19, 0, 2, 8, 13), version
    for asset in (
        "lead_evidence/format.js",
        "lead_evidence/lead_evidence.js",
        "lead_evidence/lead_evidence.xml",
        "lead_evidence/lead_evidence.scss",
    ):
        assert asset in manifest

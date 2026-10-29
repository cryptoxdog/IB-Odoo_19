"""Lock the cron registry to ir.cron XML and to the calls in the cron tests."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import defusedxml.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cron_contract import (  # noqa: E402
    CRON_TEST_FILES,
    CRONS,
    UNREACHABLE_IN_DOMAIN,
    is_cron_attribute,
    model_xml_suffix,
)

_CODE_METHOD = re.compile(r"model\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _record_bindings(xml_path: Path) -> list[tuple[str, str]]:
    """Return (model external-id tail, method) for each ir.cron record."""
    tree = ET.parse(xml_path)
    found: list[tuple[str, str]] = []
    for record in tree.iter("record"):
        if record.get("model") != "ir.cron":
            continue
        model_ref = ""
        code = ""
        for field in record.findall("field"):
            if field.get("name") == "model_id":
                model_ref = field.get("ref") or ""
            elif field.get("name") == "code":
                code = field.text or ""
        match = _CODE_METHOD.search(code)
        if not model_ref or match is None:
            continue
        found.append((model_ref.rsplit(".", 1)[-1], match.group(1)))
    return found


def _called_cron_methods(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and is_cron_attribute(node.attr):
            called.add(node.attr)
    return called


def test_registry_matches_cron_xml() -> None:
    for binding in CRONS:
        xml_path = ROOT / binding.xml_path
        assert xml_path.is_file(), binding.xml_path
        pairs = _record_bindings(xml_path)
        expected = (model_xml_suffix(binding.model), binding.method)
        assert expected in pairs, f"{binding.xml_path} has no {binding.model}.{binding.method}(); found {pairs}"


def test_unreachable_effects_are_named() -> None:
    assert set(UNREACHABLE_IN_DOMAIN) == {
        "cron_check_missing_docs",
        "cron_check_scale_tickets",
        "cron_geo_backfill",
    }
    assert all(reason.strip() for reason in UNREACHABLE_IN_DOMAIN.values())
    registered = {binding.method for binding in CRONS}
    assert set(UNREACHABLE_IN_DOMAIN) <= registered


def test_cron_test_calls_match_the_registry() -> None:
    called: set[str] = set()
    for relative in CRON_TEST_FILES:
        called.update(_called_cron_methods(ROOT / relative))
    registered = {binding.method for binding in CRONS}
    assert called == registered

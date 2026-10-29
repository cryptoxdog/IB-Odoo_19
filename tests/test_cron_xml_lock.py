"""Lock the cron registry to ir.cron XML and to the calls in the cron tests."""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter
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

_MODEL_CALL = re.compile(r"model\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_ENV_CALL = re.compile(
    r"""env\[\s*['"]([^'"]+)['"]\s*\]"""
    r"""(?:\s*\.\s*[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\))*"""
    r"""\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(""",
    re.DOTALL,
)
_REGISTERED_METHODS = {binding.method for binding in CRONS}


def _manifest_dict(manifest: Path) -> ast.Dict:
    tree = ast.parse(manifest.read_text(encoding="utf-8"), filename=str(manifest))
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
            return node.value
    raise AssertionError(f"{manifest} has no manifest dict")


def _dict_value(dict_node: ast.Dict, key: str) -> ast.AST | None:
    for dict_key, value in zip(dict_node.keys, dict_node.values, strict=True):
        if isinstance(dict_key, ast.Constant) and dict_key.value == key:
            return value
    return None


def _module_is_installable(module: Path, dict_node: ast.Dict) -> bool:
    value = _dict_value(dict_node, "installable")
    if value is None:
        return True
    if isinstance(value, ast.Constant) and isinstance(value.value, bool):
        return value.value
    raise AssertionError(f"{module / '__manifest__.py'} installable is not a boolean")


def _manifest_xml_files(root: Path) -> list[Path]:
    """XML files listed in installable addon manifests. Those are the loaded crons."""
    files: list[Path] = []
    for manifest in sorted(root.glob("*/__manifest__.py")):
        module = manifest.parent
        dict_node = _manifest_dict(manifest)
        if not _module_is_installable(module, dict_node):
            continue
        data = _dict_value(dict_node, "data")
        if data is None:
            continue
        if not isinstance(data, ast.List):
            raise AssertionError(f"{manifest} data key is not a list")
        for elt in data.elts:
            if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                raise AssertionError(f"{manifest} data list has a non-string entry")
            if elt.value.endswith(".xml"):
                files.append(module / elt.value)
    return files


def _cron_call(code: str) -> tuple[str, str]:
    """Return (env model or '', method) for the one call in an ir.cron code field."""
    model_calls = _MODEL_CALL.findall(code)
    env_calls = _ENV_CALL.findall(code)
    if len(model_calls) == 1 and not env_calls:
        return "", model_calls[0]
    if len(env_calls) == 1 and not model_calls:
        return env_calls[0]
    return "", ""


def _manifest_cron_bindings(root: Path) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return (path, model external-id tail, method) rows and parse errors."""
    found: list[tuple[str, str, str]] = []
    errors: list[str] = []
    for xml_path in _manifest_xml_files(root):
        if not xml_path.is_file():
            errors.append(f"missing manifest data file {xml_path.relative_to(root)}")
            continue
        relative = str(xml_path.relative_to(root))
        for record in ET.parse(xml_path).iter("record"):
            if record.get("model") != "ir.cron":
                continue
            model_ref = ""
            code = ""
            for field in record.findall("field"):
                if field.get("name") == "model_id":
                    model_ref = field.get("ref") or ""
                elif field.get("name") == "code":
                    code = field.text or ""
            tail = model_ref.rsplit(".", 1)[-1]
            env_model, method = _cron_call(code)
            record_id = record.get("id") or relative
            if not tail or not method:
                errors.append(f"{relative}:{record_id} has no single cron call")
                continue
            if env_model and model_xml_suffix(env_model) != tail:
                errors.append(f"{relative}:{record_id} env model {env_model} does not match {tail}")
                continue
            found.append((relative, tail, method))
    return found, errors


def _called_cron_methods(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and (is_cron_attribute(node.attr) or node.attr in _REGISTERED_METHODS):
            called.add(node.attr)
    return called


def test_registry_matches_cron_xml() -> None:
    """Every manifest-loaded ir.cron call is the registry, and the registry has no extras."""
    discovered, errors = _manifest_cron_bindings(ROOT)
    assert not errors, "unparsed manifest crons:\n" + "\n".join(errors)
    registered = [(binding.xml_path, model_xml_suffix(binding.model), binding.method) for binding in CRONS]
    assert Counter(discovered) == Counter(registered), (
        "manifest ir.cron records and CRONS diverged\n"
        f"missing from CRONS: {sorted(set(discovered) - set(registered))}\n"
        f"not in a manifest: {sorted(set(registered) - set(discovered))}"
    )


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

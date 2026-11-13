"""Every PlasticOS module page renders without the README's YAML front matter (C13 OP12-E04).

Odoo 19 (``odoo/addons/base/models/ir_module.py::_get_desc``) renders a module page
from ``<module>/static/description/index.html`` when that file exists. Otherwise it
runs docutils over ``Manifest.description`` (``odoo/modules/module.py``), which is
the manifest ``description`` when it is truthy and otherwise the raw text of the
first of ``README.rst``, ``README.md``, ``README.txt`` and ``README``. A README
that opens with YAML front matter (``readme-module-version`` keeps
``module_version`` there) would then be shown as RST text, so every PlasticOS
module whose README carries front matter must resolve to a manifest description.
The runtime witness that renders the installed pages is in
``plasticos_export/tests/test_module_pages.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README_NAMES = ("README.rst", "README.md", "README.txt", "README")
MODULES = sorted(path.parent.name for path in ROOT.glob("plasticos_*/__manifest__.py"))


def _manifest(module: str) -> dict:
    return ast.literal_eval((ROOT / module / "__manifest__.py").read_text(encoding="utf-8"))


def _front_matter_keys(text: str) -> list[str]:
    """The keys of a leading ``---`` YAML block, or [] when the text has none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    keys = []
    for line in lines[1:]:
        if line.strip() == "---":
            return keys
        if line and not line[0].isspace() and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def resolved_description(module: str) -> tuple[str, str]:
    """``(source, text)`` the way Odoo 19 picks a module page's source."""
    if (ROOT / module / "static" / "description" / "index.html").is_file():
        return "index.html", (ROOT / module / "static" / "description" / "index.html").read_text(encoding="utf-8")
    description = _manifest(module).get("description")
    if description:
        return "manifest", description
    for name in README_NAMES:
        path = ROOT / module / name
        if path.is_file():
            return name, path.read_text(encoding="utf-8")
    return "none", ""


def test_the_module_census_is_not_empty():
    assert len(MODULES) >= 30, MODULES


@pytest.mark.parametrize("module", MODULES)
def test_module_page_source_carries_no_readme_front_matter(module):
    source, text = resolved_description(module)
    keys = _front_matter_keys(text)
    assert not keys, f"{module} page renders {source} with YAML front matter keys {keys}"
    assert "module_version:" not in text, f"{module} page shows the README module_version line"


def test_front_matter_detection_is_not_vacuous():
    """The READMEs this guards against really carry front matter, so the check above can fail."""
    with_front_matter = [
        module for module in MODULES if _front_matter_keys(_readme(module)) and "module_version" in _readme(module)
    ]
    assert len(with_front_matter) >= 20, with_front_matter
    assert "module_version" in _front_matter_keys((ROOT / "plasticos_export" / "README.md").read_text("utf-8"))


def _readme(module: str) -> str:
    path = ROOT / module / "README.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""

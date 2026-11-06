"""Commercial-pipeline, foundation, and transaction module READMEs stay true to their manifests.

Reuses the front-matter, manifest, layer, and cron readers from
``tests.test_module_readme_index`` so there is one parser for every
handwritten module README. Pure Python: no Odoo, no Docker.
"""

from __future__ import annotations

import ast
import subprocess

import pytest

from tests.test_module_readme_index import (
    MANIFEST_FLAGS,
    REPO,
    _agents_layers,
    _cron_ids,
    _front_matter,
    _load_generator,
    _manifest,
)

PIPELINE_MODULES = (
    "plasticos_intake",
    "plasticos_intake_normalizer",
    "plasticos_logistics",
    "plasticos_matching",
    "plasticos_material_profile",
    "plasticos_offer",
    "plasticos_order_lines",
    "plasticos_partner_import",
    "plasticos_product",
    "plasticos_geolocalize",
    # Foundation and transaction batch. Listed by name, never discovered by a
    # directory walk: .cursorignore hides plasticos_website from editor search.
    "plasticos_website",
    "plasticos_web_leads",
    "plasticos_transaction",
    "plasticos_semantic_kernel",
    "plasticos_security_base",
    "plasticos_accounting",
    "plasticos_base",
)
# The geolocalize manifest summary says partners are geocoded on create/write.
# The module has no create/write override, so its Apps blurb states the cron instead.
RST_SUMMARY_EXEMPT = frozenset({"plasticos_geolocalize"})
RST_BOILERPLATE = ("Odoo 19.0 compatible", "Integrated with PlasticOS ecosystem")

STALE_TEXT = (
    ("plasticos_intake/README.md", "CEG HTTP POST"),
    ("plasticos_intake/README.md", "plasticos.offer.create()"),
    ("plasticos_intake/README.rst", "plasticos_processing"),
    ("plasticos_offer/README.md", "buyer_partner_id"),
    ("plasticos_offer/README.md", "offered_price"),
    ("plasticos_transaction/README.md", "refused before any write"),
    ("plasticos_transaction/README.md", "dispute"),
    ("plasticos_transaction/README.md", "db-password"),
    ("plasticos_transaction/README.rst", "depends on documents"),
    ("plasticos_accounting/README.md", "account.incoterm"),
    ("plasticos_base/README.rst", "uase"),
    ("plasticos_security_base/README.rst", "uase"),
    ("plasticos_web_leads/README.rst", "weu leads"),
)
REQUIRED_TEXT = (
    ("plasticos_logistics/README.md", "](business_rules/README.md)"),
    ("plasticos_offer/README.md", "price_per_lb"),
)


def _read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def _committed_manifest(module: str) -> dict:
    """The manifest at HEAD, so an uncommitted manifest edit cannot move the README check.

    Falls back to the working tree when git or HEAD is unavailable (an exported tree).
    """
    try:
        shown = subprocess.run(
            ["git", "show", f"HEAD:{module}/__manifest__.py"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return _manifest(module)
    return ast.literal_eval(shown.stdout)


@pytest.mark.parametrize("module", PIPELINE_MODULES)
def test_front_matter_matches_manifest(module):
    front = _front_matter(module)
    manifest = _committed_manifest(module)
    assert front["auto_generated"] is False
    assert front["component_id"] == module
    assert front["module_version"] == manifest["version"]
    assert front["depends"] == manifest["depends"]
    for key, default in MANIFEST_FLAGS:
        assert front[key] is manifest.get(key, default), f"{module}: {key}"


@pytest.mark.parametrize("module", PIPELINE_MODULES)
def test_front_matter_layer_comes_from_agents(module):
    front = _front_matter(module)
    layers = _agents_layers()
    if module in layers:
        assert front.get("layer") == layers[module]
    else:
        assert "layer" not in front


@pytest.mark.parametrize("module", PIPELINE_MODULES)
def test_front_matter_crons_exist(module):
    assert sorted(_front_matter(module)["crons"]) == sorted(_cron_ids(module))


@pytest.mark.parametrize("module", PIPELINE_MODULES)
def test_readme_rst_is_summary_and_pointer(module):
    rst = _read(f"{module}/README.rst")
    manifest = _manifest(module)
    title, underline = rst.splitlines()[:2]
    assert title == manifest["name"]
    assert set(underline) == {"#"} and len(underline) >= len(title)
    if module not in RST_SUMMARY_EXEMPT:
        assert manifest["summary"] in rst
    assert "README.md" in rst
    for line in RST_BOILERPLATE:
        assert line not in rst


@pytest.mark.parametrize(("relative", "text"), STALE_TEXT)
def test_stale_text_removed(relative, text):
    assert text not in _read(relative)


@pytest.mark.parametrize(("relative", "text"), REQUIRED_TEXT)
def test_required_text_kept(relative, text):
    assert text in _read(relative)


def test_security_base_depends_omit_commented_matching():
    assert "plasticos_matching" not in _front_matter("plasticos_security_base")["depends"]


@pytest.mark.parametrize("module", PIPELINE_MODULES)
def test_generator_leaves_page_alone(module):
    assert _load_generator().is_handwritten_readme(REPO / module / "README.md")

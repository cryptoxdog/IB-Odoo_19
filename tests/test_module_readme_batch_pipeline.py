"""Commercial-pipeline module READMEs stay true to their manifests.

Reuses the front-matter, manifest, layer, and cron readers from
``tests.test_module_readme_index`` so there is one parser for every
handwritten module README. Pure Python: no Odoo, no Docker.
"""

from __future__ import annotations

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
)
REQUIRED_TEXT = (
    ("plasticos_logistics/README.md", "](business_rules/README.md)"),
    ("plasticos_offer/README.md", "price_per_lb"),
)


def _read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("module", PIPELINE_MODULES)
def test_front_matter_matches_manifest(module):
    front = _front_matter(module)
    manifest = _manifest(module)
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


@pytest.mark.parametrize("module", PIPELINE_MODULES)
def test_generator_leaves_page_alone(module):
    assert _load_generator().is_handwritten_readme(REPO / module / "README.md")

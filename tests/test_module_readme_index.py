"""Handwritten module READMEs stay true to their manifests, and the generator leaves them alone.

Pure Python: no Odoo, no Docker. The README front matter is a derived index;
the manifest is the authority, so every drift is reported against it.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent

HANDWRITTEN_MODULES = (
    "plasticos_admin_dashboard",
    "plasticos_automation",
    "plasticos_claims",
    "plasticos_crm_bridge",
    "plasticos_crm_sync",
    "plasticos_documents",
    "plasticos_documents_native",
    "plasticos_enrichment",
    "plasticos_facility_profile",
    "plasticos_gate",
)
MANIFEST_FLAGS = (("installable", True), ("auto_install", False), ("application", False))
DOCUMENTS_MARKER = "PLASTICOS_DOCUMENTS_BRS_NATIVE_FIRST_20261026"
DOCUMENTS_MARKER_MODULES = ("plasticos_documents", "plasticos_documents_native")
LAYER_LINE = re.compile(r"^(plasticos_\w+)/\s+#\s+Layer\s+(\d+):", re.MULTILINE)
CRON_ID = re.compile(r'<record\s+id="([^"]+)"\s+model="ir\.cron"')


def _front_matter(module: str) -> dict:
    text = (REPO / module / "README.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{module}/README.md has no front matter"
    return yaml.safe_load(match.group(1))


def _manifest(module: str) -> dict:
    return ast.literal_eval((REPO / module / "__manifest__.py").read_text(encoding="utf-8"))


def _agents_layers() -> dict[str, int]:
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    return {name: int(layer) for name, layer in LAYER_LINE.findall(text)}


def _cron_ids(module: str) -> set[str]:
    """Cron xml ids declared anywhere in the module's XML, tests excluded (some live in views/)."""
    root = REPO / module
    return {
        cron
        for path in root.rglob("*.xml")
        if "tests" not in path.relative_to(root).parts
        for cron in CRON_ID.findall(path.read_text(encoding="utf-8"))
    }


@pytest.mark.parametrize("module", HANDWRITTEN_MODULES)
def test_front_matter_matches_manifest(module):
    front = _front_matter(module)
    manifest = _manifest(module)
    assert front["auto_generated"] is False
    assert front["component_id"] == module
    assert front["component_name"] == manifest["name"]
    assert front["module_version"] == manifest["version"]
    assert front["depends"] == manifest["depends"]
    for key, default in MANIFEST_FLAGS:
        assert front[key] is manifest.get(key, default), f"{module}: {key}"


@pytest.mark.parametrize("module", HANDWRITTEN_MODULES)
def test_front_matter_layer_comes_from_agents(module):
    front = _front_matter(module)
    layers = _agents_layers()
    if module in layers:
        assert front.get("layer") == layers[module]
    else:
        assert "layer" not in front, f"{module} is not in AGENTS.md Project Structure"


@pytest.mark.parametrize("module", HANDWRITTEN_MODULES)
def test_front_matter_crons_exist(module):
    crons = _front_matter(module)["crons"]
    assert sorted(crons) == sorted(_cron_ids(module))


@pytest.mark.parametrize("module", DOCUMENTS_MARKER_MODULES)
def test_documents_marker_block_kept(module):
    text = (REPO / module / "README.md").read_text(encoding="utf-8")
    begin = text.find(f"<!-- {DOCUMENTS_MARKER}_BEGIN -->")
    end = text.find(f"<!-- {DOCUMENTS_MARKER}_END -->")
    assert 0 <= begin < end


@pytest.mark.parametrize("module", HANDWRITTEN_MODULES)
def test_readme_rst_points_at_readme_md(module):
    rst = (REPO / module / "README.rst").read_text(encoding="utf-8")
    manifest = _manifest(module)
    title, underline = rst.splitlines()[:2]
    assert title == manifest["name"]
    assert set(underline) == {"#"} and len(underline) >= len(title)
    assert manifest["summary"] in rst
    assert "README.md" in rst


def _load_generator():
    path = REPO / "scripts" / "generate_subsystem_readmes.py"
    spec = importlib.util.spec_from_file_location("generate_subsystem_readmes", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generator_detects_handwritten(tmp_path):
    gen = _load_generator()
    handwritten = tmp_path / "hand.md"
    handwritten.write_text("---\nauto_generated: false\ncomponent_id: x\n---\n\n# X\n", encoding="utf-8")
    generated = tmp_path / "gen.md"
    generated.write_text('---\ncomponent_id: "x"\nlayer: "core"\n---\n\n# X\n', encoding="utf-8")
    body_only = tmp_path / "body.md"
    body_only.write_text("# X\n\nauto_generated: false\n", encoding="utf-8")
    assert gen.is_handwritten_readme(handwritten)
    assert not gen.is_handwritten_readme(generated)
    assert not gen.is_handwritten_readme(body_only)
    assert not gen.is_handwritten_readme(tmp_path / "missing.md")


@pytest.mark.parametrize("module", HANDWRITTEN_MODULES)
def test_repo_handwritten_readmes_are_detected(module):
    assert _load_generator().is_handwritten_readme(REPO / module / "README.md")


def test_generator_keeps_handwritten_and_writes_stub(tmp_path, monkeypatch, capsys):
    gen = _load_generator()
    for name in ("mod_hand", "mod_stub"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "__manifest__.py").write_text(
            "{'name': 'X', 'version': '19.0.1.0.0', 'depends': ['base']}\n", encoding="utf-8"
        )
    hand = "---\nauto_generated: false\n---\n\n# Kept by hand\n"
    (tmp_path / "mod_hand" / "README.md").write_text(hand, encoding="utf-8")
    (tmp_path / "mod_stub" / "README.md").write_text('---\ncomponent_id: "old"\n---\n\nold stub\n', encoding="utf-8")
    config = tmp_path / "config" / "subsystems"
    config.mkdir(parents=True)
    (config / "readme_config.yaml").write_text(
        yaml.safe_dump(
            {
                "subsystems": {
                    "mod_hand": {"path": "mod_hand", "tier": "core", "purpose": "p"},
                    "mod_stub": {"path": "mod_stub", "tier": "core", "purpose": "p"},
                },
                "core_docs": [],
                "template": "# {component_name}\n\n{purpose}\n",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("README_PIPELINE_CONFIG", raising=False)
    monkeypatch.setattr(sys, "argv", ["generate_subsystem_readmes.py"])
    assert gen.main() == 0
    assert (tmp_path / "mod_hand" / "README.md").read_text(encoding="utf-8") == hand
    assert (tmp_path / "mod_stub" / "README.md").read_text(encoding="utf-8") == "# Mod Stub\n\np\n"
    assert "kept 1 handwritten" in capsys.readouterr().out

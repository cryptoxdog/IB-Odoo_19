"""scripts/odoo_load_surface.py — the single owner of the Odoo install load surface.

Every rejection test first proves the passing control on the same synthetic tree.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "scripts" / "odoo_load_surface.py"


def _tree(root: Path) -> Path:
    addon = root / "plasticos_base"
    for sub in ("models", "data", "security", "tests", "i18n", "static/src", "erp_extracted_data", "demo"):
        (addon / sub).mkdir(parents=True)
    (addon / "__manifest__.py").write_text(
        "{'name': 'fixture', 'installable': True, 'depends': ['base'],\n"
        " 'data': ['security/ir.model.access.csv', 'data/seed.xml'], 'demo': ['demo/demo.xml']}\n"
    )
    (addon / "__init__.py").write_text("from . import models\n")
    (addon / "models/__init__.py").write_text("from . import model\n")
    (addon / "models/model.py").write_text("VALUE = 'A'\n")
    (addon / "data/seed.xml").write_text("<odoo/>\n")
    (addon / "data/unlisted.xml").write_text("<odoo/>\n")
    (addon / "demo/demo.xml").write_text("<odoo/>\n")
    (addon / "security/ir.model.access.csv").write_text("id,name\n")
    (addon / "tests/__init__.py").write_text("")
    (addon / "tests/test_model.py").write_text("def test():\n    pass\n")
    (addon / "i18n/fr.po").write_text('msgid "A"\nmsgstr "A"\n')
    (addon / "static/src/widget.js").write_text("export const v = 1;\n")
    (addon / "README.md").write_text("# fixture\n")
    (addon / "erp_extracted_data/grid.csv").write_text("id\n1\n")
    disabled = root / "plasticos_disabled"
    (disabled / "models").mkdir(parents=True)
    (disabled / "__manifest__.py").write_text("{'name': 'off', 'installable': False, 'data': ['missing.xml']}\n")
    (disabled / "models/model.py").write_text("VALUE = 'X'\n")
    (root / "config").mkdir()
    (root / "config/odoo.conf").write_text("[options]\n")
    (root / "requirements.txt").write_text("odoo\n")
    (root / "docs").mkdir()
    (root / "docs/guide.md").write_text("# docs\n")
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OWNER), "--root", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _surface(root: Path) -> dict[str, list[str]]:
    result = _run(root, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_surface_contains_exactly_what_odoo_reads_at_install(tmp_path: Path) -> None:
    surface = _surface(_tree(tmp_path))
    assert surface["addons"] == [
        "plasticos_base/__init__.py",
        "plasticos_base/__manifest__.py",
        "plasticos_base/data/seed.xml",
        "plasticos_base/i18n/fr.po",
        "plasticos_base/models/__init__.py",
        "plasticos_base/models/model.py",
        "plasticos_base/security/ir.model.access.csv",
        "plasticos_base/static/src/widget.js",
        "plasticos_disabled/__manifest__.py",
    ]
    assert surface["installer"] == ["config/odoo.conf", "requirements.txt"]


@pytest.mark.parametrize(
    "rel",
    [
        "plasticos_base/README.md",
        "plasticos_base/erp_extracted_data/grid.csv",
        "plasticos_base/tests/test_model.py",
        "plasticos_base/demo/demo.xml",
        "plasticos_base/data/unlisted.xml",
        "plasticos_disabled/models/model.py",
        "docs/guide.md",
    ],
)
def test_non_load_files_are_classified_other(tmp_path: Path, rel: str) -> None:
    result = _run(_tree(tmp_path), "--classify", rel)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"other\t{rel}"


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("plasticos_base/__manifest__.py", "load_surface"),
        ("plasticos_base/models/model.py", "load_surface"),
        ("plasticos_base/data/seed.xml", "load_surface"),
        ("plasticos_base/i18n/fr.po", "load_surface"),
        ("plasticos_base/static/src/widget.js", "load_surface"),
        ("config/odoo.conf", "installer"),
        ("requirements.txt", "installer"),
        ("plasticos_base/models/deleted_model.py", "load_surface"),
        ("plasticos_base/data/deleted.xml", "load_surface"),
        ("Dockerfile", "installer"),
    ],
)
def test_load_inputs_are_classified_and_exit_3(tmp_path: Path, rel: str, expected: str) -> None:
    result = _run(_tree(tmp_path), "--classify", rel)
    assert result.returncode == 3, result.stdout + result.stderr
    assert result.stdout.strip() == f"{expected}\t{rel}"


def test_untracked_python_under_addon_is_on_the_surface(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    before = _surface(root)["addons"]
    (root / "plasticos_base/models/untracked.py").write_text("VALUE = 'B'\n")
    after = _surface(root)["addons"]
    assert "plasticos_base/models/untracked.py" in after
    assert len(after) == len(before) + 1


def test_missing_declared_data_file_is_an_error_not_a_skip(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    assert _run(root, "--list").returncode == 0
    (root / "plasticos_base/data/seed.xml").unlink()
    result = _run(root, "--list")
    assert result.returncode == 2
    assert "declared file missing: data/seed.xml" in result.stderr


def test_declared_file_escaping_its_addon_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "plasticos_base/__manifest__.py").write_text("{'name': 'x', 'data': ['../config/odoo.conf']}\n")
    result = _run(root, "--list")
    assert result.returncode == 2
    assert "escapes its addon" in result.stderr


def test_unreadable_manifest_is_an_error(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "plasticos_base/__manifest__.py").write_text("{'name': 'x', 'data': [1]}\n")
    assert _run(root, "--list").returncode == 2


def test_list_and_json_agree_and_are_sorted(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    listed = _run(root, "--list").stdout.split("\n")
    listed = [line for line in listed if line]
    surface = _surface(root)
    assert listed == surface["addons"] + surface["installer"]
    assert listed == sorted(surface["addons"]) + sorted(surface["installer"])


def test_real_repository_surface_excludes_docs_fixtures_and_tests() -> None:
    surface = _surface(ROOT)
    assert surface["addons"], "the real tree must expose a non-empty load surface"
    assert not [p for p in surface["addons"] if p.endswith(".md")]
    assert not [p for p in surface["addons"] if "/erp_extracted_data/" in p]
    assert not [p for p in surface["addons"] if "/tests/" in p]
    assert "scripts/install_smoke.sh" in surface["installer"]
    assert "scripts/odoo_load_surface.py" in surface["installer"]
    for rel in surface["addons"] + surface["installer"]:
        assert (ROOT / rel).is_file(), rel

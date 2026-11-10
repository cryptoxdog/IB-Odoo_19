"""scripts/sync_readme_module_version.py keeps README module_version equal to the manifest."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_readme_module_version.py"

spec = importlib.util.spec_from_file_location("sync_readme_module_version", SCRIPT)
assert spec is not None and spec.loader is not None
sync_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_mod)

README = """---
auto_generated: false
component_id: plasticos_demo
module_version: {version}
depends:
  - base
---

# Demo

module_version: 1.0 in the body is prose and stays.
"""


@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "plasticos_demo"
    path.mkdir()
    (path / "__manifest__.py").write_text("{'name': 'Demo', 'version': '19.0.1.2.4', 'depends': ['base']}\n")
    return path


def _readme(module: Path, version: str) -> Path:
    readme = module / "README.md"
    readme.write_text(README.format(version=version), encoding="utf-8")
    return readme


@pytest.mark.parametrize("stale", ["19.0.1.2.3", '"19.0.1.2.3"', "'19.0.1.2.3'"])
def test_stale_version_is_rewritten_and_quoting_kept(module: Path, stale: str) -> None:
    readme = _readme(module, stale)
    assert sync_mod.main(["plasticos_demo/__manifest__.py"]) == 1
    text = readme.read_text(encoding="utf-8")
    quote = stale[0] if stale[0] in "\"'" else ""
    assert f"module_version: {quote}19.0.1.2.4{quote}\n" in text
    assert yaml.safe_load(text.split("---\n")[1])["module_version"] == "19.0.1.2.4"
    assert text == README.format(version=f"{quote}19.0.1.2.4{quote}")


def test_matching_version_is_a_no_op(module: Path) -> None:
    readme = _readme(module, "19.0.1.2.4")
    before = readme.stat().st_mtime_ns
    assert sync_mod.main(["plasticos_demo/__manifest__.py"]) == 0
    assert readme.stat().st_mtime_ns == before


def test_readme_without_front_matter_is_untouched(module: Path) -> None:
    readme = module / "README.md"
    readme.write_text("# Demo\n\nmodule_version: 1.0\n", encoding="utf-8")
    assert sync_mod.main(["plasticos_demo/__manifest__.py"]) == 0
    assert readme.read_text(encoding="utf-8") == "# Demo\n\nmodule_version: 1.0\n"


def test_front_matter_without_the_key_is_untouched(module: Path) -> None:
    readme = module / "README.md"
    original = "---\nauto_generated: false\n---\n\n# Demo\n"
    readme.write_text(original, encoding="utf-8")
    assert sync_mod.main(["plasticos_demo/__manifest__.py"]) == 0
    assert readme.read_text(encoding="utf-8") == original


def test_missing_readme_is_not_an_error(module: Path) -> None:
    assert sync_mod.main(["plasticos_demo/__manifest__.py"]) == 0


def test_other_paths_are_ignored(module: Path) -> None:
    readme = _readme(module, "19.0.1.2.3")
    nested = module / "sub"
    nested.mkdir()
    (nested / "__manifest__.py").write_text("{'version': '9'}\n")
    assert (
        sync_mod.main(["plasticos_demo/models/x.py", "plasticos_demo/sub/__manifest__.py", "other/__manifest__.py"])
        == 0
    )
    assert "19.0.1.2.3" in readme.read_text(encoding="utf-8")


def test_unreadable_manifest_version_fails_loudly(module: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _readme(module, "19.0.1.2.3")
    (module / "__manifest__.py").write_text("{'name': 'Demo'}\n")
    assert sync_mod.main(["plasticos_demo/__manifest__.py"]) == 1
    assert "no string 'version' key" in capsys.readouterr().err


def test_hook_is_registered_for_top_level_manifests() -> None:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}
    hook = hooks["readme-module-version"]
    assert hook["entry"] == "python3 scripts/sync_readme_module_version.py"
    assert hook["files"] == r"^plasticos_[^/]+/__manifest__\.py$"
    assert hook.get("stages") == ["pre-commit"]


def test_every_tracked_readme_already_matches_its_manifest() -> None:
    manifests = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob("plasticos_*/__manifest__.py"))
    assert manifests
    cwd = Path.cwd()
    os.chdir(ROOT)
    try:
        changed = [m for m in manifests if sync_mod.MANIFEST_PATH.match(m) and _would_change(Path(m))]
    finally:
        os.chdir(cwd)
    assert changed == []


def _would_change(manifest: Path) -> bool:
    readme = manifest.parent / "README.md"
    if not readme.is_file():
        return False
    front = sync_mod.FRONT_MATTER.match(readme.read_text(encoding="utf-8"))
    if front is None:
        return False
    line = sync_mod.VERSION_LINE.search(front.group(1))
    return line is not None and line.group(3) != sync_mod.manifest_version(manifest)

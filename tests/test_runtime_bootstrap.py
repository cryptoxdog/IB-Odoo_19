"""scripts/runtime_bootstrap.sh binds an Enterprise checkout and admits the pinned fixture.

Each test runs the real script inside a throwaway git repository whose
scripts/test_env.sh is a stub that records its arguments, with a stub `docker`
first on PATH. Real git is used for the repository, the sibling checkout and the
clone source.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "runtime_bootstrap.sh"
TEMPLATE = "odoo_test_tpl_ee_c9e8a81f52f23680"

STUB_TEST_ENV = f"""#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
env | grep -q '^TEST_ENV_ALLOW_NEW_TEMPLATE=' && echo "ALLOW_SEEN" >> "$STUB_LOG"
case "$1" in
  status) echo "template:     {TEMPLATE} (${{STUB_STATE}})" ;;
  rebuild) echo "rebuilt" ;;
esac
"""

STUB_DOCKER = """#!/usr/bin/env bash
[ "${STUB_DOCKER_UP:-1}" = "1" ] || exit 1
exit 0
"""


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _enterprise(path: Path, *, version: str = "1.0", branch: str = "19.0", git: bool = True) -> Path:
    (path / "web_enterprise").mkdir(parents=True)
    (path / "web_enterprise" / "__manifest__.py").write_text(f"{{'name': 'Web Enterprise', 'version': '{version}'}}\n")
    if git:
        _git("init", "-q", "-b", branch, cwd=path)
        _git("add", ".", cwd=path)
        _git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "seed", cwd=path)
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    parent = tmp_path / "parent"
    work = parent / "IB-Odoo_19"
    (work / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, work / "scripts" / "runtime_bootstrap.sh")
    (work / "scripts" / "test_env.sh").write_text(STUB_TEST_ENV)
    _git("init", "-q", cwd=work)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text(STUB_DOCKER)
    docker.chmod(0o755)
    return work


def _run(repo: Path, **env: str) -> subprocess.CompletedProcess[str]:
    base = {
        key: value for key, value in os.environ.items() if not key.startswith(("ODOO_ENTERPRISE_", "TEST_ENV_", "GIT_"))
    }
    base["PATH"] = f"{repo.parent.parent / 'bin'}{os.pathsep}{base.get('PATH', '')}"
    base["STUB_LOG"] = str(repo.parent.parent / "test_env.log")
    base.setdefault("STUB_STATE", "absent")
    base.update(env)
    return subprocess.run(
        ["bash", "scripts/runtime_bootstrap.sh"], cwd=repo, env=base, capture_output=True, text=True, check=False
    )


def _calls(repo: Path) -> list[str]:
    log = repo.parent.parent / "test_env.log"
    return log.read_text().splitlines() if log.exists() else []


def test_no_enterprise_refuses_and_names_the_setup(repo: Path) -> None:
    result = _run(repo)
    assert result.returncode == 2
    assert "no Odoo Enterprise checkout" in result.stderr
    assert "Cloud agent sessions" in result.stderr
    assert _calls(repo) == []


def test_unreachable_docker_refuses_before_anything_else(repo: Path) -> None:
    _enterprise(repo.parent / "odoo-enterprise")
    result = _run(repo, STUB_DOCKER_UP="0")
    assert result.returncode == 2
    assert "Docker daemon is not reachable" in result.stderr
    assert not (repo / "odoo-enterprise").exists()
    assert _calls(repo) == []


def test_sibling_checkout_is_linked_and_absent_fixture_is_rebuilt(repo: Path) -> None:
    _enterprise(repo.parent / "odoo-enterprise")
    result = _run(repo, STUB_STATE="absent")
    assert result.returncode == 0, result.stderr
    link = repo / "odoo-enterprise"
    assert link.is_symlink() and os.readlink(link) == "../odoo-enterprise"
    assert _calls(repo) == ["status", "rebuild"]
    assert "Odoo Enterprise runtime is ready" in result.stdout


def test_ready_fixture_is_reused_without_rebuild(repo: Path) -> None:
    _enterprise(repo / "odoo-enterprise")
    result = _run(repo, STUB_STATE="ready")
    assert result.returncode == 0, result.stderr
    assert _calls(repo) == ["status"]


def test_unadmitted_fixture_stops_and_names_the_operator_recovery(repo: Path) -> None:
    _enterprise(repo / "odoo-enterprise")
    result = _run(repo, STUB_STATE="not admitted for the current inputs")
    assert result.returncode == 2
    assert "make test-env-rebuild" in result.stderr
    assert _calls(repo) == ["status"]


def test_bootstrap_never_sets_the_new_template_override(repo: Path) -> None:
    _enterprise(repo / "odoo-enterprise")
    _run(repo, STUB_STATE="absent")
    assert "ALLOW_SEEN" not in _calls(repo)


def test_explicit_path_wins_over_the_local_link(repo: Path, tmp_path: Path) -> None:
    explicit = _enterprise(tmp_path / "elsewhere")
    (repo / "odoo-enterprise").mkdir()
    result = _run(repo, ODOO_ENTERPRISE_PATH=str(explicit), STUB_STATE="ready")
    assert result.returncode == 0, result.stderr
    assert f"Enterprise checkout: {explicit}" in result.stdout


def test_explicit_path_without_enterprise_refuses(repo: Path, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    result = _run(repo, ODOO_ENTERPRISE_PATH=str(tmp_path / "empty"))
    assert result.returncode == 2
    assert "has no web_enterprise/__manifest__.py" in result.stderr


def test_a_foreign_local_path_is_refused_not_replaced(repo: Path) -> None:
    (repo / "odoo-enterprise").mkdir()
    (repo / "odoo-enterprise" / "keep.txt").write_text("operator file")
    _enterprise(repo.parent / "odoo-enterprise")
    result = _run(repo)
    assert result.returncode == 2
    assert "is not an Odoo Enterprise checkout" in result.stderr
    assert (repo / "odoo-enterprise" / "keep.txt").read_text() == "operator file"


def test_wrong_qualified_series_is_refused(repo: Path) -> None:
    _enterprise(repo / "odoo-enterprise", version="18.0.1.0")
    result = _run(repo, STUB_STATE="ready")
    assert result.returncode == 2
    assert "needs series 19.0" in result.stderr


def test_wrong_branch_is_refused_for_a_series_relative_manifest(repo: Path) -> None:
    _enterprise(repo / "odoo-enterprise", branch="18.0")
    result = _run(repo, STUB_STATE="ready")
    assert result.returncode == 2
    assert "branch 18.0" in result.stderr


def test_repo_variable_clones_the_default_branch(repo: Path, tmp_path: Path) -> None:
    source = _enterprise(tmp_path / "source", branch="main")
    result = _run(repo, ODOO_ENTERPRISE_REPO=f"file://{source}", STUB_STATE="absent")
    assert result.returncode == 0, result.stderr
    assert (repo / "odoo-enterprise" / "web_enterprise" / "__manifest__.py").is_file()
    assert _calls(repo) == ["status", "rebuild"]


def test_ref_variable_selects_the_clone_branch(repo: Path, tmp_path: Path) -> None:
    source = _enterprise(tmp_path / "source", branch="main")
    _git("branch", "19.0", cwd=source)
    result = _run(repo, ODOO_ENTERPRISE_REPO=f"file://{source}", ODOO_ENTERPRISE_REF="19.0", STUB_STATE="ready")
    assert result.returncode == 0, result.stderr
    head = subprocess.run(
        ["git", "-C", str(repo / "odoo-enterprise"), "symbolic-ref", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert head.stdout.strip() == "19.0"


def test_cloned_wrong_series_branch_is_refused(repo: Path, tmp_path: Path) -> None:
    source = _enterprise(tmp_path / "source", branch="18.0")
    result = _run(repo, ODOO_ENTERPRISE_REPO=f"file://{source}")
    assert result.returncode == 2
    assert "branch 18.0" in result.stderr
    assert _calls(repo) == []


def test_main_branch_sibling_is_accepted(repo: Path) -> None:
    _enterprise(repo.parent / "odoo-enterprise", branch="main")
    result = _run(repo, STUB_STATE="ready")
    assert result.returncode == 0, result.stderr
    assert "not provable" in result.stdout


def test_malformed_repo_variable_is_refused(repo: Path) -> None:
    result = _run(repo, ODOO_ENTERPRISE_REPO="no-slash")
    assert result.returncode == 2
    assert "owner/name or a git URL" in result.stderr


def test_script_respects_the_runtime_test_ownership_contract() -> None:
    text = SCRIPT.read_text()
    assert not re.search(r"(?:\bmake|\$\{?MAKE\}?\"?)(?:\s+-\S+)*\s+runtime-test\b", text)
    assert not re.search(r"make (?:test-module|test-odoo)(?!-)", text)
    assert "TEST_ENV_ALLOW_NEW_TEMPLATE" not in text

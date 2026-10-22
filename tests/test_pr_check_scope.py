"""scripts/pr_check_run.sh — change-class gate selection and timing receipts.

Real shell, real Git (a local bare origin with a Staging branch), a fake `make`
that records the targets it was asked to build, and a stub installer that
records if it is ever called (it must not be: the Odoo install-smoke runs on
the PR in GitHub Actions). The load-surface owner is the real script.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.adversarial_contract

FAKE_MAKE = """#!/usr/bin/env bash
# Records every goal; honours FAKE_MAKE_FAIL=<goal> to fail that goal.
for goal in "$@"; do
  case "$goal" in
    -j*|--no-print-directory) continue ;;
  esac
  echo "make $goal" >> "$FAKE_MAKE_LOG"
  if [ "${FAKE_MAKE_FAIL:-}" = "$goal" ]; then exit 1; fi
done
exit 0
"""

STUB_SMOKE = """#!/usr/bin/env bash
echo "smoke $*" >> "$FAKE_MAKE_LOG"
if [ "${FAKE_SMOKE_SLEEP:-}" != "" ]; then sleep "$FAKE_SMOKE_SLEEP"; fi
exit "${FAKE_SMOKE_RC:-0}"
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    ).stdout


@dataclass
class Repo:
    root: Path
    log: Path
    env: dict[str, str]

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "scripts/pr_check_run.sh", *args],
            cwd=self.root,
            env={**self.env, **env},
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def scope(self) -> dict:
        return json.loads((self.root / ".cache/pr-check/scope.json").read_text())

    def commit(self, message: str, **files: str) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        _git(self.root, "add", "-A")
        _git(self.root, "-c", "user.name=T", "-c", "user.email=t@example.test", "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "Staging", str(origin))
    root = tmp_path / "work"
    root.mkdir()
    _git(root, "init", "-q", "-b", "Staging")
    (root / "scripts").mkdir()
    for name in ("pr_check_run.sh", "odoo_load_surface.py"):
        (root / "scripts" / name).write_text((ROOT / "scripts" / name).read_text())
    (root / "scripts/install_smoke.sh").write_text(STUB_SMOKE)
    (root / "scripts/get_odoo_module_order.py").write_text("print('plasticos_base')\n")
    addon = root / "plasticos_base"
    (addon / "data").mkdir(parents=True)
    (addon / "__manifest__.py").write_text("{'name': 'f', 'installable': True, 'data': ['data/seed.xml']}\n")
    (addon / "__init__.py").write_text("")
    (addon / "data/seed.xml").write_text("<odoo/>\n")
    (addon / "README.md").write_text("# addon docs\n")
    (root / "docs").mkdir()
    (root / "docs/guide.md").write_text("# guide\n")
    (root / "config").mkdir()
    (root / "config/odoo.conf").write_text("[options]\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=T", "-c", "user.email=t@example.test", "commit", "-q", "-m", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "origin", "Staging")
    _git(root, "checkout", "-q", "-b", "feature")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "make").write_text(FAKE_MAKE)
    (bindir / "make").chmod(0o755)
    log = tmp_path / "calls.log"
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("PR_CHECK_", "PR_BASE", "FAKE_", "COV_CORE_", "COVERAGE_", "PYTEST_"))
    }
    env.update(
        {
            "PATH": str(bindir) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            "FAKE_MAKE_LOG": str(log),
            "PR_CHECK_SKIP_REMOTE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return Repo(root, log, env)


def _no_local_smoke(calls: list[str]) -> None:
    assert not any(c.startswith("smoke ") for c in calls), "the installer must never run from the local gate"
    assert "make install-smoke" not in calls


def test_docs_only_branch_runs_only_the_light_wave(repo: Repo) -> None:
    repo.commit("docs", **{"docs/guide.md": "# changed\n", "plasticos_base/README.md": "# changed\n"})
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scope=docs_only" in result.stdout
    calls = repo.calls()
    assert "make audit-quick" in calls and "make ban-check" in calls
    assert "make test" not in calls and "make audit" not in calls and "make audit-baseline" not in calls
    _no_local_smoke(calls)
    scope = repo.scope()
    assert scope["scope"] == "docs_only" and scope["changed_count"] == 2
    assert "⏱ wave1 (audit-quick + ban-check):" in result.stdout


@pytest.mark.parametrize(
    "files,reason",
    [
        ({"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"}, "load surface"),
        (
            {"plasticos_base/__manifest__.py": "{'name': 'g', 'installable': True, 'data': ['data/seed.xml']}\n"},
            "load surface",
        ),
        ({"config/odoo.conf": "[options]\nworkers = 2\n"}, "installer"),
        ({"scripts/helper.py": "print(1)\n"}, "tooling"),
        ({"tests/test_x.py": "def test():\n    pass\n"}, "tooling"),
        ({"Makefile": "all:\n\ttrue\n"}, "tooling"),
        ({".pre-commit-config.yaml": "repos: []\n"}, "tooling"),
        ({"docs/guide.md": "# changed\n", "plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"}, "mixed"),
    ],
)
def test_load_installer_or_tooling_change_selects_full_scope(repo: Repo, files: dict, reason: str) -> None:
    repo.commit("change", **files)
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scope=full" in result.stdout, reason
    calls = repo.calls()
    assert {"make audit", "make audit-baseline", "make test"} <= set(calls)
    _no_local_smoke(calls)


def test_uncommitted_and_untracked_load_changes_also_select_full_scope(repo: Repo) -> None:
    repo.commit("docs", **{"docs/guide.md": "# changed\n"})
    (repo.root / "plasticos_base/models.py").write_text("VALUE = 1\n")  # untracked, on the surface
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scope=full" in result.stdout


def test_no_change_against_base_fails_closed_to_full(repo: Repo) -> None:
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scope=full" in result.stdout and "no change against" in result.stdout


def test_unreachable_base_fails_closed_to_full(repo: Repo) -> None:
    repo.commit("docs", **{"docs/guide.md": "# changed\n"})
    _git(repo.root, "remote", "set-url", "origin", str(repo.root / "nowhere.git"))
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scope=full" in result.stdout and "cannot fetch origin/Staging" in result.stdout


def test_forced_full_scope_overrides_docs_only(repo: Repo) -> None:
    repo.commit("docs", **{"docs/guide.md": "# changed\n"})
    result = repo.run("full", PR_CHECK_SCOPE="full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scope=full reason=forced" in result.stdout
    assert "make test" in repo.calls()


def test_classifier_error_fails_closed_to_full(repo: Repo) -> None:
    repo.commit("docs", **{"docs/guide.md": "# changed\n"})
    (repo.root / "plasticos_base/data/seed.xml").unlink()  # declared file missing: owner exits 2
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scope=full" in result.stdout


def test_load_surface_change_does_not_start_a_local_install(repo: Repo) -> None:
    # The Odoo load is proven by the "Odoo Install Smoke" workflow on the PR; a
    # local gate that still called the installer would reintroduce the ten
    # minutes this contract removes, and a stub that fails must not matter.
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    result = repo.run("full", FAKE_SMOKE_RC="1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "install-smoke" not in result.stdout
    _no_local_smoke(repo.calls())


def test_wave_one_failure_fails_the_gate(repo: Repo) -> None:
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    result = repo.run("full", FAKE_MAKE_FAIL="test")
    assert result.returncode != 0


def test_fast_mode_is_unchanged(repo: Repo) -> None:
    result = repo.run("fast")
    assert result.returncode == 0, result.stdout + result.stderr
    assert repo.calls() == ["make audit-quick", "make test"]
    assert not (repo.root / ".cache/pr-check/scope.json").exists()

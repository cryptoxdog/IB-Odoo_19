"""scripts/pr_check_scope.py and scripts/pr_check_run.sh — the local gate runs only what the branch changed can reach.

Real Git (a local bare origin with a Staging branch), a fake `make` that
records the goals it was asked to build, and a stub installer that records how
it was called. Every selection test shows the positive and the negative.
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
for goal in "$@"; do
  case "$goal" in
    -j*|--no-print-directory) continue ;;
  esac
  if [ "$goal" = "test-scoped" ]; then
    echo "make test-scoped [${TEST_PATHS:-}]" >> "$FAKE_MAKE_LOG"
  elif [ "$goal" = "runtime-test" ]; then
    echo "make runtime-test [${RUNTIME_MODULES:-}]" >> "$FAKE_MAKE_LOG"
  else
    echo "make $goal" >> "$FAKE_MAKE_LOG"
  fi
  if [ "${FAKE_MAKE_FAIL:-}" = "$goal" ]; then exit 1; fi
done
exit 0
"""

# The declared roster test_env.sh accepts: plasticos_base ships Odoo tests,
# plasticos_logistics does not, plasticos_extra is outside the roster.
STUB_ROSTER = """print("plasticos_base,plasticos_logistics")
"""

STUB_SMOKE = """#!/usr/bin/env bash
echo "smoke $*" >> "$FAKE_MAKE_LOG"
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

    def scope(self, **env: str) -> dict[str, str]:
        result = subprocess.run(
            [sys.executable, "scripts/pr_check_scope.py", "--base", "Staging"],
            cwd=self.root,
            env={**self.env, **env},
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def receipt(self) -> dict:
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
    for name in ("pr_check_run.sh", "pr_check_scope.py"):
        (root / "scripts" / name).write_text((ROOT / "scripts" / name).read_text())
    (root / "scripts/install_smoke.sh").write_text(STUB_SMOKE)
    (root / "scripts/get_odoo_module_order.py").write_text(STUB_ROSTER)
    (root / "scripts/helper.py").write_text("print(1)\n")
    (root / ".gitignore").write_text(".cache/\n")
    addon = root / "plasticos_base"
    (addon / "data").mkdir(parents=True)
    (addon / "tests").mkdir()
    (addon / "__manifest__.py").write_text("{'name': 'f', 'installable': True, 'data': ['data/seed.xml']}\n")
    (addon / "__init__.py").write_text("")
    (addon / "data/seed.xml").write_text("<odoo/>\n")
    (addon / "tests/__init__.py").write_text("from . import test_odoo\n")
    (addon / "tests/test_odoo.py").write_text("from odoo.tests import TransactionCase\n")
    extra = root / "plasticos_extra" / "tests"
    extra.mkdir(parents=True)
    (extra / "__init__.py").write_text("")
    (root / "plasticos_extra" / "models.py").write_text("VALUE = 0\n")
    (addon / "README.md").write_text("# addon docs\n")
    (root / "docs").mkdir()
    (root / "docs/guide.md").write_text("# guide\n")
    (root / "config").mkdir()
    (root / "config/odoo.conf").write_text("[options]\n")
    tests = root / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text("")
    (tests / "test_seed.py").write_text(
        "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
        'def test_seed():\n    assert (ROOT / "plasticos_base/data/seed.xml").exists()\n'
    )
    (tests / "test_conf.py").write_text('def test_conf():\n    assert "config/odoo.conf"\n')
    (tests / "test_addons.py").write_text(
        "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
        'def test_addons():\n    assert list(ROOT.glob("plasticos_*/__manifest__.py"))\n'
    )
    (tests / "test_scripts_tree.py").write_text(
        "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
        'def test_tree():\n    assert list((ROOT / "scripts").glob("*.py"))\n'
    )
    (tests / "test_helper.py").write_text('def test_helper():\n    assert "scripts/helper.py"\n')
    logistics = root / "plasticos_logistics" / "models"
    logistics.mkdir(parents=True)
    (logistics / "load.py").write_text("class Load:\n    pass\n")
    (tests / "test_word_load.py").write_text("def test_word():\n    assert 'load' == 'load'\n")
    (tests / "test_path_load.py").write_text('def test_path():\n    assert "plasticos_logistics/models/load.py"\n')
    (tests / "test_pinned.py").write_text(
        "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
        'def test_pinned():\n    assert (ROOT / "scripts" / "other.py")\n'
    )
    (tests / "test_other.py").write_text("def test_other():\n    assert True\n")
    (tests / "test_uses_other.py").write_text(
        "from tests.test_other import test_other\n\ndef test_uses():\n    test_other()\n"
    )
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
        if not k.startswith(
            (
                "PR_CHECK_",
                "PR_BASE",
                "PR_SMOKE",
                "FAKE_",
                "COV_CORE_",
                "COVERAGE_",
                "PYTEST_",
                "TEST_PATHS",
                "RUNTIME_MODULES",
            )
        )
    }
    env.pop("INSTALL_SMOKE_GATE", None)
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


# --- the owner's decisions -----------------------------------------------------


def test_documentation_only_change_reaches_nothing(repo: Repo) -> None:
    repo.commit("docs", **{"docs/guide.md": "# changed\n", "plasticos_base/README.md": "# changed\n"})
    scope = repo.scope()
    assert scope["changed"] == "2"
    assert scope["audit"] == "0" and scope["smoke"] == "0"
    assert scope["tests"] == "", "an addon README names no test path"
    repo.commit("docs", **{"docs/guide.md": "# again\n"})
    assert repo.scope()["tests"] == "", "a committed range keeps its paths"


def test_addon_load_input_change_needs_audits_smoke_and_its_readers(repo: Repo) -> None:
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    scope = repo.scope()
    assert scope["audit"] == "1" and scope["smoke"] == "1"
    assert scope["tests"] == "tests/test_seed.py"


def test_addon_odoo_test_change_needs_no_smoke(repo: Repo) -> None:
    repo.commit("odoo-test", **{"plasticos_base/tests/test_odoo.py": "from odoo.tests import TransactionCase  # x\n"})
    scope = repo.scope()
    assert scope["smoke"] == "0" and scope["audit"] == "1"
    assert scope["runtime"] == "plasticos_base", "an addon's own tests still run at runtime"


def test_runtime_selects_roster_modules_with_odoo_tests_only(repo: Repo) -> None:
    repo.commit(
        "addons",
        **{
            "plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n",
            "plasticos_logistics/models/load.py": "class Load:\n    changed = True\n",
            "plasticos_extra/models.py": "VALUE = 1\n",
        },
    )
    assert repo.scope()["runtime"] == "plasticos_base", "no tests package and outside the roster are both dropped"


def test_runtime_ignores_documentation_and_non_addon_paths(repo: Repo) -> None:
    repo.commit("docs", **{"plasticos_base/README.md": "# changed\n", "scripts/helper.py": "print(3)\n"})
    assert repo.scope()["runtime"] == ""


def test_unreadable_roster_keeps_the_whole_runtime_gate(repo: Repo) -> None:
    (repo.root / "scripts/get_odoo_module_order.py").write_text("raise SystemExit(1)\n")
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    assert repo.scope()["runtime"] == "all"


@pytest.mark.parametrize(
    "rel", ["config/odoo.conf", "scripts/install_smoke.sh", "docker-compose.yml", "requirements.txt"]
)
def test_installer_inputs_need_smoke(repo: Repo, rel: str) -> None:
    repo.commit("installer", **{rel: "changed\n"})
    assert repo.scope()["smoke"] == "1"


def test_script_change_reaches_only_a_test_that_quotes_that_file(repo: Repo) -> None:
    repo.commit("tooling", **{"scripts/helper.py": "print(2)\n"})
    scope = repo.scope()
    assert scope["smoke"] == "0" and scope["audit"] == "1"
    assert scope["tests"] == "tests/test_helper.py", "a quoted scripts directory is not a reader"


def test_model_file_selects_a_path_quote_and_not_a_bare_stem(repo: Repo) -> None:
    repo.commit("model", **{"plasticos_logistics/models/load.py": "class Load:\n    changed = True\n"})
    assert repo.scope()["tests"] == "tests/test_path_load.py"


def test_changed_test_module_selects_itself_its_importers_and_a_config_change_its_reader(repo: Repo) -> None:
    repo.commit(
        "tests",
        **{"tests/test_other.py": "def test_other():\n    assert 1\n", "config/odoo.conf": "[options]\nx = 1\n"},
    )
    assert repo.scope()["tests"] == "tests/test_conf.py tests/test_other.py tests/test_uses_other.py"


def test_dependency_manifests_are_not_documentation(repo: Repo) -> None:
    repo.commit("deps", **{"requirements-dev.txt": "pytest==8.3.5\n"})
    scope = repo.scope()
    assert scope["audit"] == "1" and scope["tests"] == "all" and scope["smoke"] == "1"
    repo.commit("notes", **{"docs/notes.txt": "plain text\n"})
    assert repo.scope()["audit"] == "1", "a committed range keeps the dependency change"


def test_uncommitted_and_untracked_changes_count(repo: Repo) -> None:
    (repo.root / "plasticos_base/data/seed.xml").write_text("<odoo><data/></odoo>\n")  # unstaged
    (repo.root / "plasticos_base/models.py").write_text("VALUE = 1\n")  # untracked
    scope = repo.scope()
    assert scope["changed"] == "2" and scope["smoke"] == "1"


@pytest.mark.parametrize(
    "files,env,reason,smoke",
    [
        ({"tests/conftest.py": "import pytest\n"}, {}, "harness", "0"),
        ({"pyproject.toml": "[tool.pytest.ini_options]\n"}, {}, "harness", "0"),
        ({"docs/guide.md": "# changed\n"}, {"PR_CHECK_SCOPE": "full"}, "forced", "1"),
    ],
)
def test_harness_changes_and_the_force_switch_run_the_whole_suite(
    repo: Repo, files: dict, env: dict, reason: str, smoke: str
) -> None:
    repo.commit("change", **files)
    scope = repo.scope(**env)
    assert scope["tests"] == "all" and scope["audit"] == "1", reason
    assert scope["smoke"] == smoke, "a harness change is not an addon or installer input"


def test_no_change_and_an_unreachable_base_keep_the_whole_gate(repo: Repo) -> None:
    scope = repo.scope()
    assert scope["changed"] == "0" and scope["tests"] == "all" and scope["smoke"] == "1"
    assert scope["runtime"] == "all"
    repo.commit("docs", **{"docs/guide.md": "# changed\n"})
    _git(repo.root, "remote", "set-url", "origin", str(repo.root / "nowhere.git"))
    scope = repo.scope()
    assert scope["changed"] == "unknown" and scope["tests"] == "all" and scope["smoke"] == "1"


# --- the runner obeys the owner -------------------------------------------------


def test_docs_only_gate_runs_no_collector_and_no_docker(repo: Repo) -> None:
    repo.commit("docs", **{"docs/guide.md": "# changed\n"})
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert repo.calls() == [], repo.calls()
    assert "install-smoke not needed" in result.stdout and "audits skipped" in result.stdout
    assert "Odoo runtime tests not needed" in result.stdout
    assert repo.receipt()["smoke"] == 0 and repo.receipt()["schema"] == "l9.pr-check-scope.v1"


def test_addon_change_reuses_smoke_evidence_without_a_fresh_upgrade(repo: Repo) -> None:
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = repo.calls()
    assert calls[:3] == [
        "make audit",
        "make audit-baseline",
        "make test-scoped [tests/test_seed.py]",
    ]
    assert "smoke --recheck" in calls
    assert "make install-smoke" not in calls
    assert "full install-smoke is optional" not in result.stdout
    assert "make test" not in calls
    assert calls[-1] == "make runtime-test [plasticos_base]"
    assert calls.index("smoke --recheck") < calls.index("make runtime-test [plasticos_base]")
    assert repo.receipt()["runtime"] == "plasticos_base"


def test_addon_test_only_change_runs_runtime_tests_without_smoke(repo: Repo) -> None:
    repo.commit("odoo-test", **{"plasticos_base/tests/test_odoo.py": "from odoo.tests import TransactionCase  # x\n"})
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = repo.calls()
    assert "smoke --recheck" not in calls and "make install-smoke" not in calls
    assert calls[-1] == "make runtime-test [plasticos_base]"


@pytest.mark.parametrize(
    "switch",
    [{"PR_SMOKE_BYPASS": "no Docker in this container"}, {"PR_CHECK_SKIP_SMOKE": "1"}],
)
def test_smoke_switches_skip_runtime_tests_and_docker(repo: Repo, switch: dict) -> None:
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    result = repo.run("full", **switch)
    assert result.returncode == 0, result.stdout + result.stderr
    calls = repo.calls()
    assert not [c for c in calls if c.startswith(("smoke", "make install-smoke", "make runtime-test"))], calls
    assert "Odoo runtime tests skipped with install-smoke" in result.stdout


def test_a_failing_runtime_test_fails_the_gate(repo: Repo) -> None:
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    result = repo.run("full", FAKE_MAKE_FAIL="runtime-test")
    assert result.returncode != 0


def test_addon_change_upgrades_when_smoke_evidence_misses(repo: Repo) -> None:
    repo.commit("load", **{"plasticos_base/data/seed.xml": "<odoo><data/></odoo>\n"})
    result = repo.run("full", FAKE_SMOKE_RC="1")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = repo.calls()
    assert "smoke --recheck" in calls and "make install-smoke" in calls


def test_test_only_change_runs_only_that_module_and_the_audits(repo: Repo) -> None:
    repo.commit("tests", **{"tests/test_other.py": "def test_other():\n    assert 1\n"})
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert repo.calls() == [
        "make audit",
        "make audit-baseline",
        "make test-scoped [tests/test_other.py tests/test_uses_other.py]",
    ]


def test_harness_change_runs_the_whole_suite(repo: Repo) -> None:
    repo.commit("harness", **{"tests/conftest.py": "import pytest\n"})
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert repo.calls() == ["make audit", "make audit-baseline", "make test"]
    assert "install-smoke not needed" in result.stdout


def test_a_failing_scope_owner_keeps_the_whole_gate(repo: Repo) -> None:
    (repo.root / "scripts/pr_check_scope.py").write_text("raise SystemExit(2)\n")
    repo.commit("docs", **{"docs/guide.md": "# changed\n"})
    result = repo.run("full")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "whole gate" in result.stdout
    assert repo.calls()[:3] == ["make audit", "make audit-baseline", "make test"]
    assert "smoke --recheck" in repo.calls()
    assert repo.calls()[-1] == "make runtime-test [all]"
    assert "full install-smoke is optional" not in result.stdout
    gated = repo.run("full")
    assert gated.returncode == 0, gated.stdout + gated.stderr
    assert repo.calls().count("smoke --recheck") >= 2
    assert not (repo.root / ".cache/pr-check/scope.json").exists(), "a stale receipt must not outlive a failed scope"


def test_a_failing_scoped_test_wave_fails_the_gate(repo: Repo) -> None:
    repo.commit("tests", **{"tests/test_other.py": "def test_other():\n    assert 1\n"})
    result = repo.run("full", FAKE_MAKE_FAIL="test-scoped")
    assert result.returncode != 0


def test_fast_mode_is_unchanged(repo: Repo) -> None:
    result = repo.run("fast")
    assert result.returncode == 0, result.stdout + result.stderr
    assert repo.calls() == ["make audit-quick", "make test"]


def test_real_repository_script_change_reaches_a_strict_subset() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from pr_check_scope import select_tests  # noqa: E402

    selected = select_tests(ROOT, ["scripts/pr_check_run.sh"])
    assert selected == ["tests/test_pr_check_scope.py"]
    docs = select_tests(ROOT, ["docs/" + "x.md"])
    assert docs == [], docs

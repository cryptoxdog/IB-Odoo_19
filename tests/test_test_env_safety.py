"""scripts/test_env.sh refuses unsafe targets before Docker is touched.

Pure-python tier: ``docker`` is a stub on PATH that records every call. A
refused target, endpoint, or project must exit 2 with no call that could
start, replace, or drop anything. The runtime behaviour (ownership markers,
leases, admission, cloning) is exercised against a real Docker daemon by
``make test-env`` / ``make test-db``; see the PR #230 evidence report.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test_env.sh"
MUTATING = (" up ", " run ", " exec ", " build", " rm ", " drop", "DROP DATABASE", "CREATE DATABASE")


def _run(tmp_path: Path, *args: str, **env: str) -> tuple[subprocess.CompletedProcess, str]:
    log = tmp_path / "docker.log"
    stub = tmp_path / "bin" / "docker"
    stub.parent.mkdir(exist_ok=True)
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo " $* " >> "{log}"\n'
        'if [ "$1" = "context" ]; then echo unix:///var/run/docker.sock; fi\n'
        "exit 0\n"
    )
    stub.chmod(0o755)
    environ = {
        "PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        **env,
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=environ, cwd=ROOT, check=False
    )
    return result, log.read_text() if log.exists() else ""


def _assert_refused(result: subprocess.CompletedProcess, calls: str, reason: str) -> None:
    assert result.returncode == 2, result.stderr
    assert "test-env refused" in result.stderr
    assert re.search(reason, result.stderr), result.stderr
    for marker in MUTATING:
        assert marker not in calls, f"{marker!r} reached docker: {calls}"


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("odoo", "not a disposable test database name"),
        ("postgres", "not a disposable test database name"),
        ("template1", "not a disposable test database name"),
        ("odoo_test", "not a disposable test database name"),
        ("ODOO_TEST_X", "not a disposable test database name"),
        ('odoo_test_x";DROP DATABASE odoo;--', "not a disposable test database name"),
        ("odoo_test_tpl_ee_0123456789abcdef", "template name"),
        ("odoo_test_bld_ce_0123456789abcdef", "template name"),
        ("odoo_test_prod_copy", "production or staging"),
        ("odoo_test_staging", "production or staging"),
    ],
)
@pytest.mark.parametrize("command", ["clone", "drop", "assert-clone", "run"])
def test_unsafe_target_is_refused_before_docker(tmp_path, command, target, reason):
    result, calls = _run(tmp_path, command, target)
    _assert_refused(result, calls, reason)
    assert calls == ""


@pytest.mark.parametrize("arg", ["-d", "-dodoo", "--database=odoo", "--db-filter=.*", "-c", "--addons-path=/tmp"])
def test_run_refuses_arguments_that_redirect_away_from_the_clone(tmp_path, arg):
    result, calls = _run(tmp_path, "run", "odoo_test_a", "--", "--test-enable", arg, "odoo")
    _assert_refused(result, calls, "redirect the run away")
    assert calls == ""


def test_business_database_name_from_env_is_refused(tmp_path):
    result, calls = _run(tmp_path, "clone", "odoo_test_live", ODOO_DB_NAME="odoo_test_live")
    _assert_refused(result, calls, "business database")


def test_remote_docker_endpoint_is_refused(tmp_path):
    result, calls = _run(tmp_path, "clone", "odoo_test_a", DOCKER_HOST="tcp://10.0.0.5:2375")
    _assert_refused(result, calls, "not the local daemon")


def test_foreign_compose_project_is_refused(tmp_path):
    result, calls = _run(tmp_path, "template", ODOO_COMPOSE_PROJECT="someone_else")
    _assert_refused(result, calls, "not this repository's stack")


def test_foreign_compose_file_is_refused(tmp_path):
    other = tmp_path / "docker-compose.yml"
    other.write_text("name: odoo19\n")
    result, calls = _run(tmp_path, "template", COMPOSE_FILE=str(other))
    _assert_refused(result, calls, "COMPOSE_FILE")


def test_unknown_parity_is_refused(tmp_path):
    result, calls = _run(tmp_path, "template", TEST_ENV_PARITY="enterprise-lite")
    _assert_refused(result, calls, "TEST_ENV_PARITY")


def test_default_clone_name_is_per_worktree_and_needs_no_docker(tmp_path):
    result, calls = _run(tmp_path, "name")
    assert result.returncode == 0, result.stderr
    assert re.fullmatch(r"odoo_test_w[0-9a-f]{10}\n", result.stdout)
    assert calls == ""
    owned, _ = _run(tmp_path, "name", TEST_ENV_OWNER="agent7")
    assert owned.stdout == "odoo_test_agent7\n"


def test_invalid_owner_is_refused(tmp_path):
    result, calls = _run(tmp_path, "name", TEST_ENV_OWNER="Agent-7; rm")
    _assert_refused(result, calls, "TEST_ENV_OWNER")


def test_makefile_test_targets_go_through_the_identity_check():
    makefile = (ROOT / "Makefile").read_text()
    assert "ifeq ($(origin ODOO_TEST_DB),file)\nODOO_TEST_DB := $(shell bash scripts/test_env.sh name)" in makefile
    for target in ("test-odoo", "test-module"):
        body = re.search(rf"(?ms)^{target}:\n(.*?)(?=^\S|\Z)", makefile).group(1)
        assert body.index("test_env.sh assert-clone $(ODOO_TEST_DB)") < body.index("docker compose run"), target
        assert "-d $(ODOO_TEST_DB)" in body, target
    erp = re.search(r"(?ms)^import-erp-test:\n(.*?)(?=^\S|\Z)", makefile).group(1)
    assert erp.index("test_env.sh assert-clone") < erp.index("$(MAKE) import-erp")

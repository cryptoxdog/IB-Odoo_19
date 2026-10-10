"""scripts/test_env.sh refuses unsafe targets before Docker is touched.

Pure-python tier: ``docker`` is a stub on PATH that records every call. A
refused target, endpoint, or project must exit 2 with no call that could
start, replace, or drop anything. The runtime behaviour (ownership markers,
leases, admission, cloning) is exercised against a real Docker daemon by
``make test-env`` / ``make test-db``; see the PR #230 evidence report.
"""

from __future__ import annotations

import json
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


def test_makefile_test_targets_run_inside_the_protected_wrapper():
    """F230-2: test and import recipes execute inside `test_env.sh run`, not after a separate check."""
    makefile = (ROOT / "Makefile").read_text()
    assert "ifeq ($(origin ODOO_TEST_DB),file)\nODOO_TEST_DB := $(shell bash scripts/test_env.sh name)" in makefile
    for target in ("test-odoo", "test-module"):
        body = re.search(rf"(?ms)^{target}:\n(.*?)(?=^\S|\Z)", makefile).group(1)
        # One shell command: the wrapper line continues straight into the compose recipe.
        assert "\tbash scripts/test_env.sh run $(ODOO_TEST_DB) -- \\\n\tdocker compose run --rm odoo \\\n" in body, (
            target
        )
        assert "-d $(ODOO_TEST_DB)" in body, target
        assert "assert-clone" not in body, target
    erp = re.search(r"(?ms)^import-erp-test:\n(.*?)(?=^\S|\Z)", makefile).group(1)
    assert "test_env.sh run $(if $(db),$(db),$(ODOO_TEST_DB)) -- \\\n\t\t$(MAKE) import-erp " in erp
    assert "assert-clone" not in erp


@pytest.mark.parametrize(
    ("args", "reason"),
    [
        (["docker", "compose", "run", "--rm", "odoo", "--test-enable", "-d", "odoo"], "redirect the run away"),
        (["docker", "compose", "run", "--rm", "odoo", "-D", "/tmp/x"], "redirect the run away"),
        (["docker", "compose", "run", "--rm", "-e", "PGHOST=prod", "odoo", "--test-enable"], "could redirect"),
        (["docker", "compose", "run", "--rm", "-e", "HOST=prod", "odoo", "--test-enable"], "could redirect"),
        (["docker", "compose", "run", "--entrypoint", "sh", "odoo"], "not accepted by run"),
        (["docker", "compose", "run", "--rm", "db", "psql"], "not accepted by run"),
        (["docker", "compose", "up", "odoo"], "accepts 'docker compose run"),
        (["make", "import-erp", "ODOO_DB_NAME=odoo"], "redirect the import away"),
        (["make", "import-erp"], "must name ODOO_DB_NAME=odoo_test_a"),
        (["make", "install-smoke"], "only 'make import-erp'"),
        (["make", "import-erp", "ODOO_DB_NAME=odoo_test_a", "COMPOSE_PROJECT_NAME=x"], "not an ERP import setting"),
        (["make", "import-erp", "ODOO_DB_NAME=odoo_test_a", "DOCKER_HOST=tcp://x"], "not an ERP import setting"),
        (["make", "import-erp", "ODOO_DB_NAME=odoo_test_a", "rebuild"], "is not accepted"),
    ],
)
def test_run_refuses_recipe_forms_that_leave_the_verified_clone(tmp_path, args, reason):
    """F230-2: the recipe and import forms are bound to the clone before Docker is touched."""
    result, calls = _run(tmp_path, "run", "odoo_test_a", "--", *args)
    _assert_refused(result, calls, reason)
    assert calls == ""


@pytest.mark.parametrize(
    "args",
    [
        ["docker", "compose", "run", "--rm", "odoo", "--test-enable", "--stop-after-init", "-d", "odoo_test_a"],
        ["--test-enable", "-u", "plasticos_transaction"],
        ["make", "import-erp", "ODOO_DB_NAME=odoo_test_a", "ERP_LIMIT=25%", "ERP_REPORT_PATH=/tmp/s.json"],
    ],
)
def test_run_accepts_the_makefile_forms_bound_to_the_clone(tmp_path, args):
    result, _ = _run(tmp_path, "run", "odoo_test_a", "--", *args)
    assert "test-env refused" not in result.stderr, result.stderr


# ---------------------------------------------------------------------------
# F230-1: a stateful docker stub answers the identity queries assert-clone makes.
# ---------------------------------------------------------------------------
_STATEFUL_STUB = r"""#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
state = json.load(open(os.environ["STUB_STATE"]))
root = os.environ["STUB_ROOT"]
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(" " + " ".join(args) + " " + chr(10))

def out(text=""):
    sys.stdout.write(text + (chr(10) if text else ""))
    sys.exit(0)

if args[:1] == ["context"]:
    out("unix:///var/run/docker.sock")
if args[:1] == ["info"]:
    out()
if args[:1] == ["compose"]:
    if "ps" in args:
        out("stubdb")
    if "config" in args:
        out('{"services": {"odoo": {}}}')
    out()
if args[:2] == ["image", "inspect"]:
    out(os.environ.get("STUB_IMAGE", "image-a"))
if args[:1] == ["inspect"]:
    out(json.dumps([{
        "Config": {"Labels": {"com.docker.compose.project": "odoo19", "com.docker.compose.service": "db",
                              "com.docker.compose.project.working_dir": root}},
        "Mounts": [{"Name": "odoo19_odoo_pgdata", "Destination": "/var/lib/postgresql/data"}],
    }]))
if args[:1] == ["exec"]:
    if "pg_isready" in args:
        out()
    query = args[args.index("-c") + 1] if "-c" in args else ""
    if "server_version_num" in query:
        out("15")
    name = query.split("datname = '")[1].split("'")[0] if "datname = '" in query else None
    if query.startswith("SELECT 1 FROM pg_database"):
        out("1" if name in state else "")
    if "shobj_description" in query and name is not None:
        out(state.get(name, ""))
    out()
out()
"""


def _stateful(tmp_path: Path, databases: dict[str, str], *args: str, **env: str) -> subprocess.CompletedProcess:
    stub = tmp_path / "sbin" / "docker"
    stub.parent.mkdir(exist_ok=True)
    stub.write_text(_STATEFUL_STUB)
    stub.chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text(json.dumps(databases))
    environ = {
        "PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "STUB_STATE": str(state),
        "STUB_ROOT": str(ROOT),
        "STUB_LOG": str(tmp_path / "stub.log"),
        "TEST_ENV_OWNER": "agenta",
        "TEST_ENV_PARITY": "community",
        **env,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=environ, cwd=ROOT, check=False
    )


def _fingerprint(tmp_path: Path, **env: str) -> str:
    status = _stateful(tmp_path, {}, "status", **env)
    assert status.returncode == 0, status.stderr
    return re.search(r"fingerprint:\s+([0-9a-f]{64})", status.stdout).group(1)


def _template(fp: str) -> tuple[str, str]:
    return (
        f"odoo_test_tpl_ce_{fp[:16]}",
        f"plasticos-test-env/2 role=template state=ready parity=ce fp={fp} builder=agentb installed=108",
    )


def _clone(fp: str, owner: str = "agenta") -> str:
    return (
        f"plasticos-test-env/2 role=clone owner={owner} parity=ce template=odoo_test_tpl_ce_{fp[:16]} fp={fp} "
        "created=2026-10-10T00:00:00Z"
    )


def test_current_owned_clone_of_the_admitted_template_is_accepted(tmp_path):
    fp = _fingerprint(tmp_path)
    tpl, marker = _template(fp)
    result = _stateful(tmp_path, {tpl: marker, "odoo_test_a": _clone(fp)}, "assert-clone", "odoo_test_a")
    assert result.returncode == 0, result.stderr
    assert f"clone of {tpl}" in result.stdout


def test_clone_is_refused_after_the_runtime_image_changes(tmp_path):
    fp = _fingerprint(tmp_path, STUB_IMAGE="image-a")
    tpl, marker = _template(fp)
    result = _stateful(
        tmp_path, {tpl: marker, "odoo_test_a": _clone(fp)}, "assert-clone", "odoo_test_a", STUB_IMAGE="image-b"
    )
    assert result.returncode == 2
    assert "is stale" in result.stderr


def test_stale_clone_of_a_still_admitted_old_template_is_refused(tmp_path):
    current = _fingerprint(tmp_path)
    old = "0" * 64
    old_tpl, old_marker = _template(old)
    new_tpl, new_marker = _template(current)
    databases = {old_tpl: old_marker, new_tpl: new_marker, "odoo_test_a": _clone(old)}
    result = _stateful(tmp_path, databases, "assert-clone", "odoo_test_a")
    assert result.returncode == 2
    assert "is stale" in result.stderr
    assert f"current inputs are {current[:16]}" in result.stderr


def test_clone_naming_a_template_that_is_not_admitted_is_refused(tmp_path):
    fp = _fingerprint(tmp_path)
    tpl, marker = _template(fp)
    result = _stateful(
        tmp_path,
        {tpl: marker.replace("state=ready", "state=building"), "odoo_test_a": _clone(fp)},
        "assert-clone",
        "odoo_test_a",
    )
    assert result.returncode == 2
    assert "not an admitted template" in result.stderr


def test_another_owners_current_clone_is_still_refused(tmp_path):
    fp = _fingerprint(tmp_path)
    tpl, marker = _template(fp)
    result = _stateful(
        tmp_path, {tpl: marker, "odoo_test_a": _clone(fp, owner="agentb")}, "assert-clone", "odoo_test_a"
    )
    assert result.returncode == 2
    assert "owned by 'agentb'" in result.stderr

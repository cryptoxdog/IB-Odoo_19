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
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test_env.sh"
MUTATING = (" up ", " run ", " exec ", " build", " rm ", " drop", "DROP DATABASE", "CREATE DATABASE")
# The rehearsal's history-mode settings (2026-11-07): census, declared digest, ledger.
HISTORY = [
    "VANILLASOFT_HISTORY_CENSUS=.l9/runtime/census.csv",
    "VANILLASOFT_HISTORY_CENSUS_SHA256=" + "a" * 64,
    "VANILLASOFT_HISTORY_CHECKPOINT=tests/production-rehearsal/evidence/run/06-crm-history.jsonl",
]


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


def test_community_parity_is_refused_outside_the_safety_harness(tmp_path):
    result, calls = _run(tmp_path, "name", TEST_ENV_PARITY="community")
    _assert_refused(result, calls, "safety harness")
    assert calls == ""


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
        (["make", "import-vanillasoft", "ODOO_DB_NAME=odoo"], "redirect the import away"),
        (["make", "import-vanillasoft", "ODOO_DB_NAME=odoo_test_a"], "requires VANILLASOFT_CALL_FLOOR"),
        (
            ["make", "import-vanillasoft", "ODOO_DB_NAME=odoo_test_a", "VANILLASOFT_API_KEY=secret"],
            "not a VanillaSoft import setting",
        ),
        # History mode (2026-11-07): the census selects it; a floor beside it, a
        # missing digest or ledger, an empty value, a permit, or a stage are refused.
        (
            [
                "make",
                "import-vanillasoft",
                "ODOO_DB_NAME=odoo_test_a",
                *HISTORY,
                "VANILLASOFT_CALL_FLOOR=2020-01-01T00:00:00Z",
            ],
            "history mode refuses VANILLASOFT_CALL_FLOOR / VANILLASOFT_CONTACT_FLOOR",
        ),
        (
            [
                "make",
                "import-vanillasoft",
                "ODOO_DB_NAME=odoo_test_a",
                *HISTORY,
                "VANILLASOFT_CONTACT_FLOOR=2020-01-01T00:00:00Z",
            ],
            "history mode refuses VANILLASOFT_CALL_FLOOR / VANILLASOFT_CONTACT_FLOOR",
        ),
        (
            ["make", "import-vanillasoft", "ODOO_DB_NAME=odoo_test_a", HISTORY[0], HISTORY[2]],
            "history mode requires VANILLASOFT_HISTORY_CENSUS_SHA256",
        ),
        (
            ["make", "import-vanillasoft", "ODOO_DB_NAME=odoo_test_a", HISTORY[0], HISTORY[1]],
            "history mode requires VANILLASOFT_HISTORY_CHECKPOINT",
        ),
        (
            ["make", "import-vanillasoft", "ODOO_DB_NAME=odoo_test_a", HISTORY[1], HISTORY[2]],
            "history mode requires VANILLASOFT_HISTORY_CENSUS",
        ),
        (
            [
                "make",
                "import-vanillasoft",
                "ODOO_DB_NAME=odoo_test_a",
                "VANILLASOFT_HISTORY_CENSUS=",
                HISTORY[1],
                HISTORY[2],
            ],
            "must name an explicit value",
        ),
        (
            ["make", "import-vanillasoft", "ODOO_DB_NAME=odoo_test_a", *HISTORY, "VANILLASOFT_HISTORY_MAX_IDS=all"],
            "must be a positive integer",
        ),
        (
            [
                "make",
                "import-vanillasoft",
                "ODOO_DB_NAME=odoo_test_a",
                *HISTORY,
                "VANILLASOFT_PRODUCTION_PERMIT=/tmp/p.json",
            ],
            "verified clone is never a production target",
        ),
        (
            ["make", "import-vanillasoft", "ODOO_DB_NAME=odoo_test_a", *HISTORY, "ODOO_STAGE=production"],
            "not a VanillaSoft import setting",
        ),
        (
            [
                "make",
                "import-erp",
                "ODOO_DB_NAME=odoo_test_a",
                "ERP_SQL_SERVER=h",
                "ERP_SQL_DATABASE=d",
                "ERP_PRODUCTION_PERMIT=/tmp/p.json",
            ],
            "verified clone is never a production target",
        ),
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
        [
            "make",
            "import-vanillasoft",
            "ODOO_DB_NAME=odoo_test_a",
            "VANILLASOFT_CALL_FLOOR=2020-01-01T00:00:00Z",
            "VANILLASOFT_CONTACT_FLOOR=2020-01-01T00:00:00Z",
        ],
        # History mode: the rehearsal's exact form (no floor), with the optional bounds.
        [
            "make",
            "import-vanillasoft",
            "ODOO_DB_NAME=odoo_test_a",
            *HISTORY,
            "VANILLASOFT_HISTORY_MAX_IDS=100",
            "VANILLASOFT_HISTORY_FAILURE_BUDGET=25",
            "VANILLASOFT_REPORT_PATH=/mnt/extra-addons/tests/production-rehearsal/evidence/run/06-crm-result.json",
        ],
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "-e",
            "VANILLASOFT_CALL_FLOOR=2020-01-01T00:00:00Z",
            "odoo",
            "--test-enable",
            "-d",
            "odoo_test_a",
        ],
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
    if "run" in args and "--test-enable" in args:
        if os.environ.get("STUB_EDIT_DURING_TEST"):
            with open(os.environ["STUB_EDIT_DURING_TEST"], "a") as edited:
                edited.write("# edited while the tests ran" + chr(10))
        sys.stdout.write(os.environ.get("STUB_ODOO_LOG", ""))
        sys.exit(int(os.environ.get("STUB_ODOO_RC", "0")))
    if "run" in args and os.environ.get("STUB_READ_STDIN"):
        with open(os.environ["STUB_LOG"], "a") as log:
            log.write(" stdin=" + repr(sys.stdin.read()) + " " + chr(10))
        out()
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
if args[:1] == ["exec"] and "-i" in args and "-c" not in args:
    # The lease session: every request ends with SELECT '<token>'; answer it.
    # STUB_LEASE_DELAY holds a grant like a competing owner would, STUB_LEASE_WRONG_TOKEN
    # answers a grant with a token that is not the requested one, STUB_LEASE_DIE ends
    # the session instead of granting. Releases are always answered.
    import re, time
    for line in sys.stdin:
        for token in re.findall(r"SELECT '([a-z]+-[0-9]+)';", line):
            if token.startswith("granted-"):
                if os.environ.get("STUB_LEASE_DIE"):
                    sys.exit(1)
                time.sleep(float(os.environ.get("STUB_LEASE_DELAY", "0")))
                if os.environ.get("STUB_LEASE_WRONG_TOKEN"):
                    token = "granted-0" + token.split("-", 1)[1]
            sys.stdout.write(token + chr(10))
            sys.stdout.flush()
    sys.exit(0)
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


def _stateful(
    tmp_path: Path,
    databases: dict[str, str],
    *args: str,
    input_text: str | None = None,
    root: Path = ROOT,
    **env: str,
) -> subprocess.CompletedProcess:
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
        "STUB_ROOT": str(root),
        "STUB_LOG": str(tmp_path / "stub.log"),
        "TEST_ENV_OWNER": "agenta",
        "TEST_ENV_PARITY": "community",
        "TEST_ENV_SAFETY_HARNESS": "1",
        "TEST_ENV_EVIDENCE_DIR": str(tmp_path / "evidence"),
        **env,
    }
    return subprocess.run(
        ["bash", str(root / "scripts" / "test_env.sh"), *args],
        capture_output=True,
        text=True,
        env=environ,
        cwd=root,
        check=False,
        input=input_text,
    )


def _status(tmp_path: Path, root: Path = ROOT, **env: str) -> dict:
    """One `status` observation: its fingerprint, addon source and input lines.

    Callers that need several values of the same unchanged state read them from
    one observation. Nothing is cached: every call runs the script again.
    """
    status = _stateful(tmp_path, {}, "status", root=root, **env)
    assert status.returncode == 0, status.stderr
    return {
        "fingerprint": re.search(r"fingerprint:\s+([0-9a-f]{64})", status.stdout).group(1),
        "source": re.search(r"source:\s+([0-9a-f]{64})", status.stdout).group(1),
        "inputs": [
            line.split("  input  ", 1)[1] for line in status.stdout.splitlines() if line.startswith("  input  ")
        ],
    }


def _fingerprint(tmp_path: Path, root: Path = ROOT, **env: str) -> str:
    return _status(tmp_path, root=root, **env)["fingerprint"]


def _source(tmp_path: Path, root: Path = ROOT, **env: str) -> str:
    return _status(tmp_path, root=root, **env)["source"]


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


PINNED_FIXTURE = "odoo_test_tpl_ee_c9e8a81f52f23680"


def _enterprise(tmp_path: Path) -> dict[str, str]:
    return {
        "TEST_ENV_PARITY": "enterprise",
        "ODOO_ENTERPRISE_PATH": str(tmp_path / "missing-enterprise"),
    }


def _ee_template(fp: str) -> str:
    return f"plasticos-test-env/2 role=template state=ready parity=ee fp={fp} builder=agentb installed=169"


def _ee_clone(fp: str) -> str:
    return (
        f"plasticos-test-env/2 role=clone owner=agenta parity=ee template={PINNED_FIXTURE} fp={fp} "
        "created=2026-10-10T00:00:00Z"
    )


def _inputs(tmp_path: Path, **env: str) -> list[str]:
    return _status(tmp_path, **env)["inputs"]


def _sha256(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


# Calls that would change a database. The stateful harness also sees `compose build`
# (a cached image build), which is not one of them.
DB_MUTATING = ("COMMENT ON", "DROP", "CREATE DATABASE", "RENAME", " run ", "IS_TEMPLATE")


def test_enterprise_status_names_only_the_pinned_fixture(tmp_path):
    pin = (ROOT / "config" / "test_env_fixture.conf").read_text()
    assert f"TEMPLATE={PINNED_FIXTURE}" in pin
    env = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **env)
    status = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(fp)}, "status", **env)
    assert status.returncode == 0, status.stderr
    assert f"template:     {PINNED_FIXTURE} (ready)" in status.stdout
    assert "canonical" in status.stdout


def test_enterprise_status_does_not_call_a_fixture_admitted_for_other_inputs_ready(tmp_path):
    """F261-1: the pinned name alone is not admission; its fp must be the current inputs."""
    status = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template("ab" * 32)}, "status", **_enterprise(tmp_path))
    assert status.returncode == 0, status.stderr
    assert f"template:     {PINNED_FIXTURE} (not admitted for the current inputs)" in status.stdout


def test_clone_of_a_fixture_admitted_for_other_inputs_is_refused(tmp_path):
    """F261-1: a current clone does not make its incompatible fixture usable."""
    env = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **env)
    databases = {PINNED_FIXTURE: _ee_template("ab" * 32), "odoo_test_a": _ee_clone(fp)}
    result = _stateful(tmp_path, databases, "assert-clone", "odoo_test_a", **env)
    assert result.returncode == 2, result.stderr
    assert "not an admitted template for the current inputs" in result.stderr


def test_unproven_fixture_is_refused_and_not_rebuilt(tmp_path):
    """F261-1: no recorded inputs hash to the fixture's fp, so nothing proves it compatible."""
    env = _enterprise(tmp_path)
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template("ab" * 32)}, "template", **env)
    assert result.returncode == 2, result.stderr
    assert "is unproven for the current inputs" in result.stderr
    assert "not rebuilt or replaced" in result.stderr
    calls = (tmp_path / "stub.log").read_text()
    for marker in DB_MUTATING:
        assert marker not in calls, f"{marker!r} reached docker: {calls}"


def test_surviving_inputs_name_the_drift_and_do_not_restamp(tmp_path):
    """A name-generation file that does not hash to the comment cannot re-stamp.

    When its lines differ, the refusal names the drifted key and the rebuild command.
    """
    env = _enterprise(tmp_path)
    recorded = ["image=content:older" if line.startswith("image=") else line for line in _inputs(tmp_path, **env)]
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / f"{PINNED_FIXTURE}.inputs.txt").write_text("\n".join(recorded) + "\n")
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template("cd" * 32)}, "template", **env)
    assert result.returncode == 2, result.stderr
    assert "image changed" in result.stderr
    assert "make test-env-rebuild" in result.stderr
    assert "COMMENT ON" not in (tmp_path / "stub.log").read_text()
    for marker in DB_MUTATING:
        assert marker not in (tmp_path / "stub.log").read_text()


def test_rebuild_refuses_when_the_fixture_is_already_admitted(tmp_path):
    env = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **env)
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(fp)}, "rebuild", **env)
    assert result.returncode == 2, result.stderr
    assert "already admitted for the current inputs" in result.stderr
    calls = (tmp_path / "stub.log").read_text()
    for marker in DB_MUTATING:
        assert marker not in calls, f"{marker!r} reached docker: {calls}"


def test_inputs_file_that_does_not_hash_to_the_fixture_fp_is_not_proof(tmp_path):
    env = _enterprise(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / f"{PINNED_FIXTURE}.inputs.txt").write_text("\n".join(_inputs(tmp_path, **env)) + "\n")
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template("cd" * 32)}, "template", **env)
    assert result.returncode == 2, result.stderr
    assert "is unproven for the current inputs" in result.stderr
    assert "COMMENT ON" not in (tmp_path / "stub.log").read_text()


@pytest.mark.parametrize("key", ["image", "postgres", "modules", "config", "enterprise"])
def test_fixture_admitted_for_other_inputs_is_refused_by_name(tmp_path, key):
    """F261-1: image, Postgres, roster, configuration, or Enterprise drift rejects the fixture."""
    env = _enterprise(tmp_path)
    recorded = [f"{line}-admitted-earlier" if line.startswith(f"{key}=") else line for line in _inputs(tmp_path, **env)]
    assert any(line.startswith(f"{key}=") for line in recorded), recorded
    text = "\n".join(recorded) + "\n"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / f"{PINNED_FIXTURE}.inputs.txt").write_text(text)
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(_sha256(text))}, "template", **env)
    assert result.returncode == 2, result.stderr
    assert f"is incompatible with the current inputs: {key} changed" in result.stderr
    assert "not rebuilt or replaced" in result.stderr
    calls = (tmp_path / "stub.log").read_text()
    for marker in DB_MUTATING:
        assert marker not in calls, f"{marker!r} reached docker: {calls}"


def test_fixture_recorded_with_addon_source_is_certified_without_a_rebuild(tmp_path):
    """F261-1: a fixture admitted while addon source was in its fp is proved by its inputs file."""
    env = _enterprise(tmp_path)
    observed = _status(tmp_path, **env)
    fp, current = observed["fingerprint"], observed["inputs"]
    at = next(i for i, line in enumerate(current) if line.startswith("config="))
    recorded = current[:at] + ["addons=" + "e" * 64] + current[at:]
    text = "\n".join(recorded) + "\n"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / f"{PINNED_FIXTURE}.inputs.txt").write_text(text)
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(_sha256(text))}, "template", **env)
    assert result.returncode == 0, result.stderr
    assert "matches the current inputs" in result.stdout
    calls = (tmp_path / "stub.log").read_text()
    assert f'COMMENT ON DATABASE "{PINNED_FIXTURE}" IS ' in calls
    assert f" fp={fp} " in calls
    for marker in ("DROP", "CREATE DATABASE", "RENAME", " run ", "IS_TEMPLATE"):
        assert marker not in calls, f"{marker!r} reached docker: {calls}"
    assert _sha256((evidence / f"{PINNED_FIXTURE}.inputs.txt").read_text()) == fp


def test_enterprise_clone_of_another_template_is_refused(tmp_path):
    env = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **env)
    other = "odoo_test_tpl_ee_" + ("f" * 16)
    databases = {
        PINNED_FIXTURE: (
            f"plasticos-test-env/2 role=template state=ready parity=ee fp={fp} builder=agentb installed=169"
        ),
        "odoo_test_a": (
            f"plasticos-test-env/2 role=clone owner=agenta parity=ee template={other} fp={fp} "
            "created=2026-10-10T00:00:00Z"
        ),
    }
    result = _stateful(tmp_path, databases, "assert-clone", "odoo_test_a", **env)
    assert result.returncode == 2, result.stderr
    assert PINNED_FIXTURE in result.stderr
    assert other in result.stderr


def test_new_enterprise_template_is_refused_in_the_script():
    source = SCRIPT.read_text()
    assert '[ "${TEST_ENV_ALLOW_NEW_TEMPLATE:-}" != "$PINNED_TEMPLATE" ]' in source
    assert (
        "A new template is not created unless that database is absent and TEST_ENV_ALLOW_NEW_TEMPLATE equals its name"
        in source
    )
    assert '[ -z "$PINNED_TEMPLATE" ] && adopt_admitted_template' in source


# ---------------------------------------------------------------------------
# F261-2: a --test-enable run upgrades the PlasticOS roster on the clone and is
# judged by Odoo's own test summary.
# ---------------------------------------------------------------------------
ROSTER = subprocess.run(
    ["python3", str(ROOT / "scripts" / "get_odoo_module_order.py")], capture_output=True, text=True, check=True
).stdout.strip()
TEST_RECIPE = ["docker", "compose", "run", "--rm", "odoo", "--test-enable", "--stop-after-init"]


def _summary(failed: int, errors: int, total: int, db: str = "odoo_test_a") -> str:
    return (
        "2026-10-19 00:00:00,000 1 INFO odoo_test_a odoo.modules.loading: loading 169 modules...\n"
        f"2026-10-19 00:00:09,000 1 INFO {db} odoo.tests.result: "
        f"{failed} failed, {errors} error(s) of {total} tests when loading database '{db}'\n"
    )


def _test_run(tmp_path: Path, *recipe: str, root: Path = ROOT, **env: str) -> subprocess.CompletedProcess:
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, root=root, **base)
    databases = {PINNED_FIXTURE: _ee_template(fp), "odoo_test_a": _ee_clone(fp)}
    return _stateful(tmp_path, databases, "run", "odoo_test_a", "--", *recipe, root=root, **base, **env)


def _odoo_call(tmp_path: Path) -> str:
    calls = [line for line in (tmp_path / "stub.log").read_text().splitlines() if "--test-enable" in line]
    assert len(calls) == 1, calls
    return calls[0]


def test_full_suite_upgrades_the_roster_and_reports_the_count(tmp_path):
    """make test-odoo: every declared PlasticOS module is upgraded on the clone, not -u all."""
    result = _test_run(
        tmp_path, *TEST_RECIPE, "-d", "odoo_test_a", "--log-level=test", STUB_ODOO_LOG=_summary(0, 0, 37)
    )
    assert result.returncode == 0, result.stderr
    assert "tests: 37 run, 0 failed, 0 error(s) on odoo_test_a (scope roster" in result.stdout
    call = _odoo_call(tmp_path)
    assert f" -u {ROSTER} " in call
    assert " -u all " not in call
    tags = ",".join(f"/{m}" for m in ROSTER.split(","))
    assert f" --test-tags {tags} " in call
    assert " -d odoo_test_a " in call
    receipt = _receipt(tmp_path)
    assert receipt["tests"] == 37
    assert receipt["template"] == PINNED_FIXTURE
    assert (receipt["failed"], receipt["errors"], receipt["exit"]) == (0, 0, 0)
    assert receipt["head"] == _git(ROOT, "rev-parse", "HEAD")
    assert isinstance(receipt["dirty"], bool)


def test_module_test_upgrades_the_roster_and_runs_only_that_module(tmp_path):
    """make test-module m=...: the dependencies on disk are applied, the tests are that module's."""
    result = _test_run(
        tmp_path,
        *TEST_RECIPE,
        "-d",
        "odoo_test_a",
        "--log-level=test",
        "-u",
        "plasticos_commission",
        STUB_ODOO_LOG=_summary(0, 0, 4),
    )
    assert result.returncode == 0, result.stderr
    assert "scope plasticos_commission" in result.stdout
    call = _odoo_call(tmp_path)
    assert f" -u {ROSTER} " in call
    assert " --test-tags /plasticos_commission " in call


# ---------------------------------------------------------------------------
# F261-4: the receipt names the source that was tested. The fingerprint leaves
# addon source out, so the receipt carries the addon digest, the Git head, and
# whether the worktree differed from that head.
# ---------------------------------------------------------------------------
_CHECKOUT_FILES = (
    "scripts/test_env.sh",
    "scripts/get_odoo_module_order.py",
    "config/test_env_fixture.conf",
    "config/odoo_module_order.yaml",
    "docker-compose.yml",
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()


def _git_checkout(tmp_path: Path) -> tuple[Path, str]:
    """A committed copy of the runner and its inputs with one PlasticOS addon file; returns (root, head)."""
    root = tmp_path / "checkout"
    for rel in _CHECKOUT_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    (root / "plasticos_base").mkdir()
    (root / "plasticos_base" / "__init__.py").write_text("# fixture addon\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    identity = {
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    head = subprocess.run(
        ["git", "-C", str(root), "commit-tree", _git(root, "write-tree"), "-m", "fixture"],
        capture_output=True,
        text=True,
        env={**os.environ, **identity},
        check=True,
    ).stdout.strip()
    _git(root, "update-ref", "HEAD", head)
    return root, head


def _receipt(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "evidence" / "odoo_test_a.test-receipt.json").read_text())


def test_receipt_binds_the_tested_source_to_a_clean_head(tmp_path):
    root, head = _git_checkout(tmp_path)
    source = _source(tmp_path, root=root, **_enterprise(tmp_path))
    result = _test_run(tmp_path, *TEST_RECIPE, "-d", "odoo_test_a", root=root, STUB_ODOO_LOG=_summary(0, 0, 37))
    assert result.returncode == 0, result.stderr
    receipt = _receipt(tmp_path)
    assert (receipt["head"], receipt["dirty"], receipt["source"]) == (head, False, source)


@pytest.mark.parametrize(
    ("path", "addon"),
    [
        ("plasticos_base/__init__.py", True),  # uncommitted edit of a tracked addon file
        ("plasticos_base/models.py", True),  # untracked addon file the container loads
        ("docs/notes.md", False),  # a change outside the addons still is not the head
    ],
)
def test_receipt_of_a_worktree_that_differs_from_its_head_is_dirty(tmp_path, path, addon):
    """A receipt never claims a clean head for source that is not that head."""
    root, head = _git_checkout(tmp_path)
    clean = _source(tmp_path, root=root, **_enterprise(tmp_path))
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    with (root / path).open("a") as handle:
        handle.write("# not committed\n")
    result = _test_run(tmp_path, *TEST_RECIPE, "-d", "odoo_test_a", root=root, STUB_ODOO_LOG=_summary(0, 0, 37))
    assert result.returncode == 0, result.stderr
    receipt = _receipt(tmp_path)
    assert receipt["head"] == head
    assert receipt["dirty"] is True
    assert (receipt["source"] != clean) is addon


def test_addon_source_changed_during_the_run_leaves_no_receipt(tmp_path):
    """The digest is of the bytes Odoo loaded: an edit during the run is not the tested source."""
    root, _ = _git_checkout(tmp_path)
    result = _test_run(
        tmp_path,
        *TEST_RECIPE,
        "-d",
        "odoo_test_a",
        root=root,
        STUB_ODOO_LOG=_summary(0, 0, 37),
        STUB_EDIT_DURING_TEST=str(root / "plasticos_base" / "__init__.py"),
    )
    assert result.returncode != 0, result.stdout
    assert "changed during the run" in result.stderr, result.stderr
    assert not (tmp_path / "evidence" / "odoo_test_a.test-receipt.json").exists()


@pytest.mark.parametrize(
    ("log", "rc", "reason"),
    [
        (_summary(0, 0, 0), 0, "zero tests ran"),
        (_summary(2, 0, 30), 1, "2 failed, 0 error"),
        (_summary(0, 1, 30), 1, "0 failed, 1 error"),
        (_summary(0, 0, 30), 1, "odoo exited with status 1"),
        ("odoo.modules.loading: Modules loaded.\n", 0, "no Odoo test summary"),
        (_summary(0, 0, 30, db="odoo_test_b"), 0, "no Odoo test summary"),
    ],
)
def test_test_run_without_passing_tests_fails(tmp_path, log, rc, reason):
    """F261-2: a clean exit is not a pass. No summary, no tests, or a failure fails the run."""
    result = _test_run(tmp_path, *TEST_RECIPE, "-d", "odoo_test_a", STUB_ODOO_LOG=log, STUB_ODOO_RC=str(rc))
    assert result.returncode != 0, result.stdout
    assert "test-env refused" not in result.stderr
    assert reason in result.stderr, result.stderr


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        (["-u", "plasticos_dev_tools"], "not a declared PlasticOS module"),
        (["-u", "base"], "not a declared PlasticOS module"),
        (["-u", "all"], "not a declared PlasticOS module"),
        (["-u", "plasticos_base", "-u", "plasticos_offer"], "one -u list"),
        (["-i", "plasticos_base"], "not accepted in a test run"),
        (["--test-tags=/base"], "not accepted in a test run"),
        (["--log-level=debug"], "not accepted in a test run"),
    ],
)
def test_test_run_scope_is_refused_before_docker(tmp_path, extra, reason):
    result, calls = _run(tmp_path, "run", "odoo_test_a", "--", *TEST_RECIPE, "-d", "odoo_test_a", *extra)
    _assert_refused(result, calls, reason)
    assert calls == ""


# ---------------------------------------------------------------------------
# F261-3: a guarded import cannot leave the verified clone through make.
# ---------------------------------------------------------------------------
VANILLASOFT = [
    "make",
    "import-vanillasoft",
    "ODOO_DB_NAME=odoo_test_a",
    "VANILLASOFT_CALL_FLOOR=2020-01-01T00:00:00Z",
    "VANILLASOFT_CONTACT_FLOOR=2020-01-01T00:00:00Z",
]
# 2026-11-10 (operator decision): import-vanillasoft writes only the Odoo.sh
# production database over SSH and refuses inside a verified clone, so the
# guarded-import contract below is proven on import-erp, the import that still
# runs on the clone. VANILLASOFT stays the form test_env.sh admits before make
# refuses it.
VS_CLONE_REFUSAL = (
    "import-vanillasoft refused: this target writes the Odoo.sh production database "
    "and does not run inside a test-env clone"
)
ERP_IMPORT = [
    "make",
    "import-erp",
    "ODOO_DB_NAME=odoo_test_a",
    "ERP_SQL_SERVER=erp-host.invalid",
    "ERP_SQL_DATABASE=erp_probe",
]


def test_guarded_import_cannot_be_redirected_by_an_injected_makefile(tmp_path):
    """Real make, real Makefile, stub docker: an `override` in MAKEFILES would name the business database."""
    injected = tmp_path / "inject.mk"
    injected.write_text("override ODOO_DB_NAME = odoo\n")
    probe = subprocess.run(
        ["make", "-n", *ERP_IMPORT[1:]],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "MAKEFILES": str(injected)},
        check=False,
    )
    assert "shell -d odoo " in probe.stdout, "the injection must redirect an unguarded make, or this proves nothing"

    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    databases = {PINNED_FIXTURE: _ee_template(fp), "odoo_test_a": _ee_clone(fp)}
    result = _stateful(
        tmp_path,
        databases,
        "run",
        "odoo_test_a",
        "--",
        *ERP_IMPORT,
        **base,
        MAKEFILES=str(injected),
        MAKEFLAGS="ODOO_DB_NAME=odoo",
        GNUMAKEFLAGS="ODOO_DB_NAME=odoo",
    )
    assert result.returncode == 0, result.stderr
    shells = [line for line in (tmp_path / "stub.log").read_text().splitlines() if " shell " in line]
    assert len(shells) == 1, shells
    assert " shell -d odoo_test_a --no-http " in shells[0]


def test_guarded_make_starts_with_the_clone_marker_and_without_make_environment(tmp_path):
    fake = tmp_path / "fakemake"
    fake.mkdir()
    dump = tmp_path / "make-env.json"
    (fake / "make").write_text(
        "#!/usr/bin/env python3\nimport json, os, sys\n"
        f"json.dump({{'argv': sys.argv[1:], 'env': dict(os.environ)}}, open({str(dump)!r}, 'w'))\n"
    )
    (fake / "make").chmod(0o755)
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    databases = {PINNED_FIXTURE: _ee_template(fp), "odoo_test_a": _ee_clone(fp)}
    result = _stateful(
        tmp_path,
        databases,
        "run",
        "odoo_test_a",
        "--",
        str(fake / "make"),
        *VANILLASOFT[1:],
        **base,
        MAKEFILES="/tmp/x.mk",
        MAKEFLAGS="-e",
        MFLAGS="-e",
        GNUMAKEFLAGS="-e",
    )
    assert result.returncode == 0, result.stderr
    seen = json.loads(dump.read_text())
    assert seen["argv"] == VANILLASOFT[1:]
    for name in ("MAKEFILES", "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS"):
        assert name not in seen["env"], name
    assert seen["env"]["TEST_ENV_VERIFIED_CLONE"] == "odoo_test_a"
    assert seen["env"]["COMPOSE_PROJECT_NAME"] == "odoo19"
    assert seen["env"]["COMPOSE_FILE"] == str(ROOT / "docker-compose.yml")


def _make_import(
    tmp_path: Path, target: str, *args: str, docker_up: bool, **env: str
) -> tuple[subprocess.CompletedProcess, str, Path]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "docker.log"
    (bindir / "docker").write_text(
        "#!/usr/bin/env bash\n"
        f'echo " $* " >> "{log}"\n' + ("" if docker_up else '[ "$1" = info ] && exit 1\n') + "exit 0\n"
    )
    (bindir / "docker").chmod(0o755)
    # Any SSH or SCP to the production host is recorded, never sent.
    for tool in ("ssh", "scp"):
        (bindir / tool).write_text(f'#!/usr/bin/env bash\necho "{tool} $*" >> "{tmp_path / "net.log"}"\nexit 0\n')
        (bindir / tool).chmod(0o755)
    venv = tmp_path / "venv" / "bin"
    venv.mkdir(parents=True)
    ran = tmp_path / "odoo.log"
    (venv / "odoo").write_text(f'#!/usr/bin/env bash\necho "$*" >> "{ran}"\n')
    (venv / "odoo").chmod(0o755)
    environ = {
        **os.environ,
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "TEST_ENV_VERIFIED_CLONE": "odoo_test_a",
        **env,
    }
    result = subprocess.run(
        ["make", target, *args, f"L9_ODOO_VENV={venv.parent}"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=environ,
        check=False,
    )
    return result, log.read_text() if log.exists() else "", ran


@pytest.mark.parametrize(
    ("target", "args"),
    [
        ("import-erp", ["ERP_DRY=1"]),
    ],
)
def test_import_recipe_refuses_a_database_other_than_the_verified_clone(tmp_path, target, args):
    result, calls, ran = _make_import(tmp_path, target, "ODOO_DB_NAME=odoo", *args, docker_up=True)
    assert result.returncode != 0
    assert "is not the verified clone odoo_test_a" in result.stderr
    assert calls == ""
    assert not ran.exists()


@pytest.mark.parametrize(
    ("target", "args"),
    [
        ("import-erp", ["ERP_DRY=1"]),
    ],
)
def test_import_recipe_refuses_the_no_docker_fallback_for_a_verified_clone(tmp_path, target, args):
    result, _, ran = _make_import(tmp_path, target, "ODOO_DB_NAME=odoo_test_a", *args, docker_up=False)
    assert result.returncode != 0
    assert "the no-Docker harness is another server" in result.stderr
    assert not ran.exists(), ran.read_text()


@pytest.mark.parametrize("db", ["odoo_test_a", "odoo"])
@pytest.mark.parametrize("docker_up", [True, False])
@pytest.mark.parametrize("args", [[], ["VANILLASOFT_CALL_FLOOR=2020-01-01T00:00:00Z"]])
def test_import_vanillasoft_refuses_any_verified_clone_before_its_mode_guard(tmp_path, db, docker_up, args):
    """import-vanillasoft writes only Odoo.sh production; inside a verified clone it refuses first."""
    result, calls, ran = _make_import(
        tmp_path,
        "import-vanillasoft",
        f"ODOO_DB_NAME={db}",
        *args,
        docker_up=docker_up,
        ODOO_SH_PRODUCTION_SSH="12345@probe.odoo.invalid",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert VS_CLONE_REFUSAL in result.stderr
    assert "no mode selected" not in result.stderr
    assert calls == ""
    assert not ran.exists()
    assert not (tmp_path / "net.log").exists(), (tmp_path / "net.log").read_text()


@pytest.mark.parametrize(
    "form",
    [
        ["--test-en", "--stop-after-init"],
        ["-t", "/plasticos_base", "--stop-after-init"],
        ["-t/plasticos_base"],
        ["--test-tags=/plasticos_base"],
        ["--test-tags", "/plasticos_base"],
        ["--test-file=x.py"],
        ["--test-enable=1"],
    ],
)
def test_every_form_that_starts_odoo_tests_belongs_to_the_runner(tmp_path, form):
    """Odoo enables tests for test tags alone and accepts option prefixes; none of these skips the runner."""
    result, calls = _run(tmp_path, "run", "odoo_test_a", "--", *form)
    _assert_refused(result, calls, "not accepted in a test run")
    assert calls == ""


@pytest.mark.parametrize(
    "arg",
    [
        "--db_h=other",
        "--db_po=5433",
        "--db_us=x",
        "--db_pa=x",
        "--datab=odoo",
        "--pg_p=/x",
        "--addons=/x",
        "--conf=/x",
        "-cFILE",
        "-rodoo",
        "-wsecret",
        "-D/tmp/x",
    ],
)
def test_abbreviated_options_that_redirect_the_run_are_refused(tmp_path, arg):
    result, calls = _run(tmp_path, "run", "odoo_test_a", "--", "shell", arg)
    _assert_refused(result, calls, "redirect the run away")
    assert calls == ""


def test_abbreviated_database_option_with_a_separate_value_is_refused(tmp_path):
    result, calls = _run(tmp_path, "run", "odoo_test_a", "--", "shell", "--datab", "odoo")
    _assert_refused(result, calls, "redirect the run away")


def test_fixture_with_a_differing_line_that_has_no_simple_key_is_refused(tmp_path):
    """The decision compares the whole text; naming the change is only for the message."""
    env = _enterprise(tmp_path)
    text = "\n".join([*_inputs(tmp_path, **env), "Odoo_Src-2=extra"]) + "\n"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / f"{PINNED_FIXTURE}.inputs.txt").write_text(text)
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(_sha256(text))}, "template", **env)
    assert result.returncode == 2, result.stderr
    assert "is incompatible with the current inputs" in result.stderr
    assert "COMMENT ON" not in (tmp_path / "stub.log").read_text()


def _owned_clone_run(tmp_path: Path, *recipe: str, clone_extra: str = "", **env: str):
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    databases = {PINNED_FIXTURE: _ee_template(fp), "odoo_test_a": _ee_clone(fp) + clone_extra}
    return _stateful(tmp_path, databases, "run", "odoo_test_a", "--", *recipe, **base, **env)


def _upgrade_calls(tmp_path: Path) -> list[str]:
    return [
        line
        for line in (tmp_path / "stub.log").read_text().splitlines()
        if " compose " in line and " run " in line and f" -u {ROSTER} " in line and "--test-enable" not in line
    ]


def test_guarded_import_runs_on_a_clone_upgraded_to_the_source_on_disk(tmp_path):
    """An import loads current code; the clone's PlasticOS schema is upgraded first, once per source."""
    base = _enterprise(tmp_path)
    source = _source(tmp_path, **base)
    result = _owned_clone_run(tmp_path, *ERP_IMPORT)
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "stub.log").read_text()
    upgrades = _upgrade_calls(tmp_path)
    assert len(upgrades) == 1, log
    assert " -d odoo_test_a " in upgrades[0]
    assert log.index(upgrades[0]) < log.index(" shell -d odoo_test_a ")
    assert 'COMMENT ON DATABASE "odoo_test_a" IS ' in log
    assert f" src={source}'" in log


def test_clone_already_upgraded_for_this_source_is_not_upgraded_again(tmp_path):
    base = _enterprise(tmp_path)
    source = _source(tmp_path, **base)
    result = _owned_clone_run(tmp_path, *ERP_IMPORT, clone_extra=f" src={source}")
    assert result.returncode == 0, result.stderr
    assert _upgrade_calls(tmp_path) == []


def test_guarded_run_of_import_vanillasoft_is_refused_by_its_recipe(tmp_path):
    """test_env.sh admits the form, then the recipe refuses: no Odoo shell runs on the clone or anywhere."""
    result = _owned_clone_run(tmp_path, *VANILLASOFT)
    assert result.returncode == 2, result.stdout + result.stderr
    assert VS_CLONE_REFUSAL in result.stderr
    assert " shell " not in (tmp_path / "stub.log").read_text()


def test_failed_upgrade_stops_the_import(tmp_path):
    stub = (
        "#!/usr/bin/env bash\n"
        'if [ "$1" = compose ] && [[ " $* " == *" -u "* ]] && [[ " $* " != *" --test-enable "* ]]; then exit 1; fi\n'
        f'exec "{tmp_path / "sbin" / "docker"}" "$@"\n'
    )
    wrapper = tmp_path / "wrap"
    wrapper.mkdir()
    (wrapper / "docker").write_text(stub)
    (wrapper / "docker").chmod(0o755)
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    databases = {PINNED_FIXTURE: _ee_template(fp), "odoo_test_a": _ee_clone(fp)}
    result = _stateful(
        tmp_path,
        databases,
        "run",
        "odoo_test_a",
        "--",
        *VANILLASOFT,
        **base,
        PATH=f"{wrapper}{os.pathsep}{tmp_path / 'sbin'}{os.pathsep}{os.environ['PATH']}",
    )
    assert result.returncode != 0
    assert "upgrading the PlasticOS roster on odoo_test_a failed" in result.stderr
    assert " shell " not in (tmp_path / "stub.log").read_text()


def test_upgrade_stage_does_not_consume_the_piped_shell_script(tmp_path):
    """runtime-gate-f1 pipes its gate into `run <db> -- shell`; the upgrade must not read it."""
    result = _owned_clone_run(tmp_path, "shell", input_text="print('gate')\n", STUB_READ_STDIN="1")
    assert result.returncode == 0, result.stderr
    stdins = [line.strip() for line in (tmp_path / "stub.log").read_text().splitlines() if line.startswith(" stdin=")]
    assert stdins == ["stdin=''", "stdin=\"print('gate')\\n\""], stdins


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


def test_clone_stage_is_retained_until_marker_is_written():
    source = SCRIPT.read_text()
    stage = source.split("odoo_stage() {", 1)[1].split("\n}\n", 1)[0]
    clone = source.split("clone_template() {", 1)[1].split("\n}\n", 1)[0]

    assert '[[ "$stage" != clone-* ]]' in stage
    duplicate = 'odoo_db "$stage" duplicate "$TEMPLATE_DB" "$target"'
    assert clone.count(duplicate) == 2
    for tail in clone.split(duplicate)[1:]:
        assert tail.index('set_comment "$target"') < tail.index('docker rm "$cname"')
    resume = clone.split('echo "→ resuming the interrupted clone', 1)[1].split("return 0", 1)[0]
    assert 'lease "tpl:$TEMPLATE_DB" shared' in resume
    assert "template_ready || refuse" in resume


def test_retirement_protects_detached_build_stages():
    source = SCRIPT.read_text()
    refs = source.split("template_references() {", 1)[1].split("\n}\n", 1)[0]
    retire = source.split("retire_own_templates() {", 1)[1].split("\n}\n", 1)[0]

    assert '[[ "$1" == odoo_test_bld_* ]]' in refs
    assert "(init|install|reseed)$" in refs
    assert refs.count("|| return 1") >= 3
    assert 'references="$(template_references "$name")" ||' in retire
    assert 'if [ -n "$references" ]; then' in retire


# ---------------------------------------------------------------------------
# Leases: `drop` takes the database lease before anything else, and an absent
# database is refused only after the lease is granted. That refusal is the proof
# the lease was (or was not) held.
# ---------------------------------------------------------------------------
def _drop(tmp_path: Path, **env: str) -> subprocess.CompletedProcess:
    return _stateful(tmp_path, {}, "drop", "odoo_test_a", **env)


def test_lease_granted_late_is_awaited_and_reports_the_wait(tmp_path):
    result = _drop(tmp_path, STUB_LEASE_DELAY="2.2")
    assert "waiting for lease 'db:odoo_test_a'" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 2, result.stderr
    assert "odoo_test_a does not exist" in result.stderr


def test_lease_answered_with_another_token_times_out_on_elapsed_time(tmp_path):
    import time

    started = time.monotonic()
    result = _drop(tmp_path, STUB_LEASE_WRONG_TOKEN="1", TEST_ENV_LOCK_TIMEOUT="1")
    elapsed = time.monotonic() - started
    assert result.returncode == 1, result.stderr
    assert "timed out after 1s waiting for lease 'db:odoo_test_a'" in result.stderr
    assert "does not exist" not in result.stderr
    assert 1 <= elapsed < 6, elapsed


def test_lease_session_that_ends_without_a_grant_fails_closed(tmp_path):
    result = _drop(tmp_path, STUB_LEASE_DIE="1")
    assert result.returncode == 1, result.stderr
    assert "lease session ended" in result.stderr
    assert "does not exist" not in result.stderr


# ---------------------------------------------------------------------------
# 2026-11-12 (Export campaign S3, C02-REAUTH-3): an installable module listed
# under excluded_modules is test-scoped only when the admitted fixture has it
# installed. Its state is read from the verified clone, a copy of the fixture.
# ---------------------------------------------------------------------------
_MODULE_STATE_STUB = _STATEFUL_STUB.replace(
    '    if "shobj_description" in query and name is not None:\n',
    '    if "FROM ir_module_module" in query:\n'
    '        out(os.environ.get("STUB_MODULE_STATE", ""))\n'
    '    if "shobj_description" in query and name is not None:\n',
)


def _excluded_test_run(tmp_path: Path, module_state: str) -> subprocess.CompletedProcess:
    assert _MODULE_STATE_STUB != _STATEFUL_STUB
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    stub = tmp_path / "sbin" / "docker"
    stub.parent.mkdir(exist_ok=True)
    stub.write_text(_MODULE_STATE_STUB)
    stub.chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({PINNED_FIXTURE: _ee_template(fp), "odoo_test_a": _ee_clone(fp)}))
    environ = {
        "PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "STUB_STATE": str(state),
        "STUB_ROOT": str(ROOT),
        "STUB_LOG": str(tmp_path / "stub.log"),
        "STUB_MODULE_STATE": module_state,
        "STUB_ODOO_LOG": _summary(0, 0, 12),
        "TEST_ENV_OWNER": "agenta",
        "TEST_ENV_PARITY": "community",
        "TEST_ENV_SAFETY_HARNESS": "1",
        "TEST_ENV_EVIDENCE_DIR": str(tmp_path / "evidence"),
        **base,
    }
    recipe = [*TEST_RECIPE, "-d", "odoo_test_a", "--log-level=test", "-u", "plasticos_documents_native"]
    return subprocess.run(
        ["bash", str(ROOT / "scripts" / "test_env.sh"), "run", "odoo_test_a", "--", *recipe],
        capture_output=True,
        text=True,
        env=environ,
        cwd=ROOT,
        check=False,
    )


def test_excluded_module_installed_in_the_fixture_is_test_scoped(tmp_path):
    """plasticos_documents_native auto-installs on the Enterprise fixture: its tests run, tagged like the roster."""
    result = _excluded_test_run(tmp_path, "installed")
    assert result.returncode == 0, result.stderr
    assert "scope plasticos_documents_native" in result.stdout
    call = _odoo_call(tmp_path)
    assert f" -u {ROSTER} " in call
    assert "plasticos_documents_native" not in ROSTER.split(",")
    assert " --test-tags /plasticos_documents_native " in call


@pytest.mark.parametrize("module_state", ["", "uninstalled", "to install"])
def test_excluded_module_not_installed_in_the_fixture_is_refused(tmp_path, module_state):
    """An excluded module the fixture does not have installed is refused before Odoo runs."""
    result = _excluded_test_run(tmp_path, module_state)
    assert result.returncode != 0, result.stdout
    assert "test-env refused" in result.stderr
    assert "is excluded from the roster and is not installed in the admitted fixture" in result.stderr
    calls = (tmp_path / "stub.log").read_text()
    assert "--test-enable" not in calls


# ---------------------------------------------------------------------------
# 2026-11-12 (Export campaign S6, C06-RECON F4/F8). F4: a template is admitted
# only from a tree whose PlasticOS addons equal its Git head, and the ready
# marker names that head; `status` shows it. F8: `migrate <db> <from-rev>`
# upgrades an owned clone made in another checkout when only the roster grew,
# and a migrated clone is checked against the template admitted for its old
# inputs. backup/restore use Odoo's own database manager.
# ---------------------------------------------------------------------------
def _template_build(tmp_path: Path, root: Path) -> subprocess.CompletedProcess:
    return _stateful(tmp_path, {}, "template", root=root)


def test_template_admission_is_refused_from_a_dirty_addon_tree(tmp_path):
    root, head = _git_checkout(tmp_path)
    (root / "plasticos_base" / "__init__.py").write_text("# edited, not committed\n")
    result = _template_build(tmp_path, root)
    assert result.returncode == 2, result.stdout
    assert "differs from its Git head" in result.stderr
    assert head[:12] in result.stderr
    calls = (tmp_path / "stub.log").read_text()
    assert " run " not in calls and "COMMENT ON" not in calls


def test_template_admission_from_a_clean_tree_is_not_refused_for_its_source(tmp_path):
    root, _ = _git_checkout(tmp_path)
    (root / "notes.txt").write_text("outside the addon paths\n")
    result = _template_build(tmp_path, root)
    assert "differs from its Git head" not in result.stderr
    # The source check passed: the build went on to the next gate (this fixture checkout
    # has one addon, so the module preflight is what stops it).
    assert "declared modules not found on any addons path" in result.stderr


def test_template_ready_marker_records_the_source_head_and_digest():
    script = (ROOT / "scripts" / "test_env.sh").read_text()
    assert "$(template_source_marker) $ADMISSION" in script
    assert 'echo "srchead=$(git -C "$ROOT" rev-parse --verify -q HEAD) srcdigest=$(addon_source)"' in script


@pytest.mark.parametrize(
    ("extra", "expected"), [(" srchead=abc123 srcdigest=def456", "head abc123, addons def456"), ("", "not recorded")]
)
def test_status_shows_the_template_source(tmp_path, extra, expected):
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(fp) + extra}, "status", **base)
    assert result.returncode == 0, result.stderr
    assert f"template src: {expected}" in result.stdout


def _migration_case(
    tmp_path: Path, *, owner: str = "agenta", template_fp: str | None = None, evidence: bool = True, drop_first=False
) -> tuple[Path, str, dict, str]:
    """A checkout, its head, the env, and the old fp of a clone made before plasticos_export joined the roster."""
    root, head = _git_checkout(tmp_path)
    base = _enterprise(tmp_path)
    current = _status(tmp_path, root=root, **base)["inputs"]
    old = []
    for line in current:
        if line.startswith("modules="):
            modules = line.split("=", 1)[1].split(",")
            assert modules[-1] == "plasticos_export"
            modules = modules[1:-1] if drop_first else modules[:-1]
            line = "modules=" + ",".join(modules)
        old.append(line)
    text = "\n".join(old) + "\n"
    old_fp = _sha256(text)
    if evidence:
        (tmp_path / "evidence").mkdir(exist_ok=True)
        (tmp_path / "evidence" / f"{PINNED_FIXTURE}.inputs.txt").write_text(text)
    clone = (
        f"plasticos-test-env/2 role=clone owner={owner} parity=ee template={PINNED_FIXTURE} fp={old_fp} "
        "created=2026-11-12T00:00:00Z"
    )
    databases = {PINNED_FIXTURE: _ee_template(template_fp or old_fp), "odoo_test_a": clone}
    return root, head, {"databases": databases, **base}, old_fp


def _migrate(tmp_path: Path, root: Path, rev: str, case: dict) -> subprocess.CompletedProcess:
    databases = case.pop("databases")
    return _stateful(tmp_path, databases, "migrate", "odoo_test_a", rev, root=root, **case)


def test_migrate_upgrades_the_roster_installs_the_added_module_and_stamps_the_lineage(tmp_path):
    root, head, case, old_fp = _migration_case(tmp_path)
    result = _migrate(tmp_path, root, head, case)
    assert result.returncode == 0, result.stderr
    assert "migrated to" in result.stdout
    calls = (tmp_path / "stub.log").read_text()
    run = [line for line in calls.splitlines() if " -i plasticos_export " in line]
    assert len(run) == 1, calls
    assert " -u " in run[0] and ",plasticos_export" not in run[0].split(" -u ", 1)[1].split(" ", 1)[0]
    assert " -d odoo_test_a " in run[0]
    stamp = [line for line in calls.splitlines() if "COMMENT ON DATABASE" in line and "odoo_test_a" in line]
    assert stamp and f"migrated_from={old_fp}" in stamp[-1] and f"fromrev={head}" in stamp[-1]
    assert (tmp_path / "evidence" / "odoo_test_a.migrate.log").exists()


@pytest.mark.parametrize(
    ("kwargs", "rev", "reason"),
    [
        ({"owner": "agentb"}, None, "owned by 'agentb'"),
        ({"template_fp": "f" * 64}, None, "not the template admitted"),
        ({"evidence": False}, None, "migration source is unproven"),
        ({"drop_first": True}, None, "with modules appended"),
        ({}, "not-a-sha", "needs the source revision"),
        ({}, "0123456", "is not a commit"),
    ],
)
def test_migrate_refuses_an_unproven_or_unsupported_migration(tmp_path, kwargs, rev, reason):
    root, head, case, _ = _migration_case(tmp_path, **kwargs)
    result = _migrate(tmp_path, root, rev or head, case)
    assert result.returncode == 2, result.stdout
    assert re.search(reason, result.stderr), result.stderr
    calls = (tmp_path / "stub.log").read_text()
    assert " -i plasticos_export" not in calls and "COMMENT ON" not in calls


def test_migrate_refuses_when_another_fingerprint_config_file_changed(tmp_path):
    root, head, case, _ = _migration_case(tmp_path)
    with (root / "docker-compose.yml").open("a") as handle:
        handle.write("# local edit\n")
    result = _migrate(tmp_path, root, head, case)
    assert result.returncode == 2, result.stdout
    assert re.search("recorded config digest|other than config/odoo_module_order.yaml", result.stderr), result.stderr
    assert " -i plasticos_export" not in (tmp_path / "stub.log").read_text()


def test_migrate_refuses_a_clone_that_already_matches_the_current_inputs(tmp_path):
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    result = _stateful(
        tmp_path,
        {PINNED_FIXTURE: _ee_template(fp), "odoo_test_a": _ee_clone(fp)},
        "migrate",
        "odoo_test_a",
        _git(ROOT, "rev-parse", "HEAD"),
        **base,
    )
    assert result.returncode == 2
    assert "nothing to migrate" in result.stderr


def _migrated_clone(fp_now: str, old_fp: str) -> str:
    return (
        f"plasticos-test-env/2 role=clone owner=agenta parity=ee template={PINNED_FIXTURE} fp={fp_now} "
        f"created=2026-11-12T00:00:00Z migrated_from={old_fp} fromrev={'a' * 40} src={'b' * 64}"
    )


def test_a_migrated_clone_is_checked_against_the_template_of_its_old_inputs(tmp_path):
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    old_fp = "c" * 64
    accepted = _stateful(
        tmp_path,
        {PINNED_FIXTURE: _ee_template(old_fp), "odoo_test_a": _migrated_clone(fp, old_fp)},
        "assert-clone",
        "odoo_test_a",
        **base,
    )
    assert accepted.returncode == 0, accepted.stderr
    refused = _stateful(
        tmp_path,
        {PINNED_FIXTURE: _ee_template("d" * 64), "odoo_test_a": _migrated_clone(fp, old_fp)},
        "assert-clone",
        "odoo_test_a",
        **base,
    )
    assert refused.returncode == 2
    assert "was migrated from inputs cccccccccccccccc" in refused.stderr


@pytest.mark.parametrize(
    ("args", "reason"),
    [
        (["backup", "odoo"], "not a disposable test database name"),
        (["backup", "odoo_test_tpl_ee_c9e8a81f52f23680"], "template name"),
        (["restore", "odoo_test_a", "odoo_test_a"], "target other than the backed-up clone"),
        (["restore", "odoo_test_a", "odoo_prod"], "not a disposable test database name"),
        (["restore", "odoo_test_a", "odoo_test_staging"], "production or staging"),
        (["migrate", "odoo"], "not a disposable test database name"),
    ],
)
def test_backup_restore_and_migrate_refuse_unsafe_names_before_docker(tmp_path, args, reason):
    result, calls = _run(tmp_path, *args)
    _assert_refused(result, calls, reason)
    assert calls == ""


def test_restore_refuses_a_backup_that_no_longer_matches_its_checksum(tmp_path):
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    backup = tmp_path / "evidence" / "backup"
    backup.mkdir(parents=True)
    (backup / "odoo_test_a.zip").write_bytes(b"changed after the backup")
    (backup / "odoo_test_a.zip.json").write_text(json.dumps({"sha256": "0" * 64, "marker": _ee_clone(fp)}))
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(fp)}, "restore", "odoo_test_a", "odoo_test_b", **base)
    assert result.returncode == 2
    assert "no longer matches its recorded checksum" in result.stderr
    assert " load " not in (tmp_path / "stub.log").read_text()


def test_restore_loads_with_odoo_and_stamps_the_restored_lineage(tmp_path):
    base = _enterprise(tmp_path)
    fp = _fingerprint(tmp_path, **base)
    backup = tmp_path / "evidence" / "backup"
    backup.mkdir(parents=True)
    content = b"PK synthetic"
    (backup / "odoo_test_a.zip").write_bytes(content)
    import hashlib

    sha = hashlib.sha256(content).hexdigest()
    (backup / "odoo_test_a.zip.json").write_text(json.dumps({"sha256": sha, "marker": _ee_clone(fp)}))
    result = _stateful(tmp_path, {PINNED_FIXTURE: _ee_template(fp)}, "restore", "odoo_test_a", "odoo_test_b", **base)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "stub.log").read_text()
    assert " load odoo_test_b /var/lib/odoo/restore-odoo_test_b.zip " in calls
    stamp = [line for line in calls.splitlines() if "COMMENT ON DATABASE" in line and "odoo_test_b" in line]
    assert stamp and "restored_from=odoo_test_a" in stamp[-1] and f"backup={sha}" in stamp[-1]
    assert "role=clone owner=agenta" in stamp[-1]

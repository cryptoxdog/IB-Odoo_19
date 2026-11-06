"""``make import-erp`` hands the importer the ERP SQL password exactly as given.

Pure-python tier. The real Makefile runs from a scratch directory whose
``docker`` is a stub that records the ``ERP_SQL_PASSWORD=`` argument it is
given, so no container or database is touched.

SQL Server answers a changed password with the same error 18456 as a wrong
one. The recipe writes the value inside double quotes in a shell command, so
make used to expand ``$`` in it and the shell ran backticks and broke on ``"``.
A value in ``.env`` also silently replaced the caller's password, because make
gives a makefile assignment precedence over the environment.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

_DOCKER_STUB = """#!/usr/bin/env bash
if [ "$1" = "info" ]; then exit 0; fi
for arg in "$@"; do
  case "$arg" in
    ERP_SQL_PASSWORD=*) printf '%s' "${arg#ERP_SQL_PASSWORD=}" > "$CAPTURE" ;;
  esac
done
exit 0
"""

_NESTED = f"""nested:
\t@$(MAKE) -s --no-print-directory -f {MAKEFILE} import-erp ODOO_DB_NAME=probe_db
"""

PASSWORDS = [
    "plain-not-a-real-secret",
    "ab$Xcd",
    "a`id -u`b",
    'q"uo"te',
    "back\\slash",
    "it's",
    "sp ace",
    "p(a)r,en",
    "$$dbl",
    "end$",
]


def _run(tmp_path: Path, *, env_pw=None, cmdline_pw=None, dotenv=None, nested=False, extra_env=None, target=None):
    work = tmp_path / "work"
    work.mkdir()
    (work / "plasticos_partner_import").symlink_to(ROOT / "plasticos_partner_import")
    if dotenv is not None:
        (work / ".env").write_text(dotenv, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(_DOCKER_STUB, encoding="utf-8")
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    capture = tmp_path / "password.txt"

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("ERP_SQL", "MAKE")) and key not in {"MFLAGS", "TEST_ENV_VERIFIED_CLONE"}
    }
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["CAPTURE"] = str(capture)
    if env_pw is not None:
        env["ERP_SQL_PASSWORD"] = env_pw
    env.update(extra_env or {})

    argv = ["make", "-s", "--no-print-directory", "-C", str(work), "-f", str(MAKEFILE)]
    if nested:
        extra = tmp_path / "nested.mk"
        extra.write_text(_NESTED, encoding="utf-8")
        argv += ["-f", str(extra), "nested"]
    else:
        argv += [target or "import-erp", "ODOO_DB_NAME=probe_db"]
    if cmdline_pw is not None:
        argv.append(f"ERP_SQL_PASSWORD={cmdline_pw}")
    result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120, check=False)  # noqa: S603
    received = capture.read_text(encoding="utf-8") if capture.exists() else None
    return result, received


@pytest.mark.parametrize("password", PASSWORDS)
@pytest.mark.parametrize("route", ["environment", "command line", "nested make"])
def test_password_reaches_the_importer_unchanged(tmp_path, route, password):
    if route == "command line":
        result, received = _run(tmp_path, cmdline_pw=password)
    else:
        result, received = _run(tmp_path, env_pw=password, nested=route == "nested make")
    assert result.returncode == 0, result.stderr
    assert received == password


def test_dotenv_password_is_used_when_the_caller_sets_none(tmp_path):
    result, received = _run(tmp_path, dotenv="ERP_SQL_PASSWORD=from-dotenv-not-a-real-secret\n")
    assert result.returncode == 0, result.stderr
    assert received == "from-dotenv-not-a-real-secret"


def test_matching_dotenv_password_is_accepted(tmp_path):
    secret = "same-not-a-real-secret"
    result, received = _run(tmp_path, env_pw=secret, dotenv=f"ERP_SQL_PASSWORD={secret}\n")
    assert result.returncode == 0, result.stderr
    assert received == secret


def test_matching_dotenv_password_is_accepted_in_a_nested_make(tmp_path):
    secret = "same-not-a-real-secret"
    result, received = _run(tmp_path, env_pw=secret, dotenv=f"ERP_SQL_PASSWORD={secret}\n", nested=True)
    assert result.returncode == 0, result.stderr
    assert received == secret


@pytest.mark.parametrize("dotenv_value", ["other-not-a-real-secret", ""])
def test_dotenv_password_that_differs_from_the_caller_is_refused(tmp_path, dotenv_value):
    caller = "caller-not-a-real-secret"
    result, received = _run(tmp_path, env_pw=caller, dotenv=f"ERP_SQL_PASSWORD={dotenv_value}\n")
    assert result.returncode != 0
    assert received is None, "the importer must not be started"
    assert "differs from the one in .env" in result.stderr
    output = result.stdout + result.stderr
    assert caller not in output
    if dotenv_value:
        assert dotenv_value not in output


def test_makefile_change_only_adds_lines():
    """Makefile is additive_only (ops/config/root-file-protection.json): the fix adds, never rewrites."""
    text = MAKEFILE.read_text(encoding="utf-8")
    assert '-e ERP_SQL_PASSWORD="$(ERP_SQL_PASSWORD)"' in text
    assert 'ERP_SQL_PASSWORD="$(ERP_SQL_PASSWORD)"' in text
    assert text.index("ERP_SQL_PASSWORD_BEFORE_ENV := $(value ERP_SQL_PASSWORD)") < text.index("-include .env")
    assert "import-erp: import-erp-password-guard" in text


REFERENCE_TEXT = "${ERP_SQL_PASSWORD_RAW}"


@pytest.mark.parametrize("route", ["environment", "command line"])
def test_password_equal_to_the_reference_text_is_kept(tmp_path, route):
    """A top-level make resolves the caller's value even when it reads like the internal reference."""
    if route == "command line":
        result, received = _run(tmp_path, cmdline_pw=REFERENCE_TEXT)
    else:
        result, received = _run(tmp_path, env_pw=REFERENCE_TEXT)
    assert result.returncode == 0, result.stderr
    assert received == REFERENCE_TEXT


@pytest.mark.parametrize("password", ["caller-not-a-real-secret", REFERENCE_TEXT])
def test_stale_inherited_raw_value_is_ignored_at_top_level(tmp_path, password):
    result, received = _run(tmp_path, env_pw=password, extra_env={"ERP_SQL_PASSWORD_RAW": "stale-not-a-real-secret"})
    assert result.returncode == 0, result.stderr
    assert received == password


def test_dotenv_conflict_is_refused_through_a_nested_make(tmp_path):
    """The outer make finds the conflict; the nested import-erp must still refuse."""
    caller = "caller-not-a-real-secret"
    result, received = _run(tmp_path, env_pw=caller, dotenv="ERP_SQL_PASSWORD=other-not-a-real-secret\n", nested=True)
    assert result.returncode != 0
    assert received is None, "the importer must not be started"
    assert "differs from the one in .env" in result.stderr


def test_import_erp_test_refuses_a_dotenv_conflict_before_it_starts(tmp_path):
    caller = "caller-not-a-real-secret"
    result, received = _run(
        tmp_path, env_pw=caller, dotenv="ERP_SQL_PASSWORD=other-not-a-real-secret\n", target="import-erp-test"
    )
    assert result.returncode != 0
    assert received is None
    assert "differs from the one in .env" in result.stderr
    assert caller not in result.stdout + result.stderr

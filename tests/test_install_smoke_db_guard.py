"""Smoke-database identity refuses before any destructive Docker command.

The install-smoke script used to drop whatever ``ODOO_INSTALL_SMOKE_DB`` named.
These tests stub ``docker`` and assert terminate/drop/create/build/up/push do
not run unless the disposable database and endpoint are proven.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "install_smoke.sh"
DESTRUCTIVE_MARKERS = (
    " pg_terminate_backend",
    "DROP DATABASE",
    " compose up",
    " compose build",
    " compose create",
    " compose push",
    " compose rm",
    " compose down",
)


def _docker_stub(log_path: Path, *, inspect_json: str | None, container_id: str) -> str:
    inspect_literal = "None" if inspect_json is None else repr(inspect_json)
    return f"""#!/usr/bin/env python3
import os
import sys

log = {str(log_path)!r}
with open(log, "a", encoding="utf-8") as handle:
    handle.write(" ".join(sys.argv[1:]) + "\\n")
args = sys.argv[1:]
if "inspect" in args:
    payload = {inspect_literal}
    if payload is None:
        sys.exit(1)
    sys.stdout.write(payload)
    sys.exit(0)
if "ps" in args and "-q" in args:
    cid = {container_id!r}
    if cid:
        print(cid)
    sys.exit(0)
if "ps" in args:
    sys.exit(0)
if "config" in args:
    sys.stdout.write("  db:\\n    POSTGRES_PASSWORD: stub\\n")
    sys.exit(0)
if "pg_isready" in args:
    sys.exit(0)
if any("SELECT state FROM ir_module_module" in arg for arg in args):
    print("installed")
    sys.exit(0)
if "xmlsec" in " ".join(args):
    print("xmlsec stub")
    sys.exit(0)
sys.exit(0)
"""


def _run(
    tmp_path: Path, env_extra: dict[str, str], *, inspect_json: str | None = None, container_id: str = ""
) -> subprocess.CompletedProcess[str]:
    log_path = tmp_path / "docker.log"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "docker"
    stub.write_text(_docker_stub(log_path, inspect_json=inspect_json, container_id=container_id), encoding="utf-8")
    stub.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE_", "COVERAGE_"))}
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["POSTGRES_PASSWORD"] = "stub-not-a-secret"
    env["ODOO_ENTERPRISE_MODULES"] = "none"
    env.update(env_extra)
    return subprocess.run(
        ["bash", str(SMOKE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
        env=env,
    )


def _docker_log(tmp_path: Path) -> str:
    log_path = tmp_path / "docker.log"
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")


def _assert_no_destructive(log: str) -> None:
    for marker in DESTRUCTIVE_MARKERS:
        assert marker not in f" {log}", f"destructive command ran ({marker.strip()}):\n{log}"


@pytest.mark.parametrize(
    "name",
    [
        "odoo",
        "postgres",
        "template0",
        "template1",
        "Production",
        "production",
        "cieTrade",
        "ERP",
        "odoo_install_smoke;DROP DATABASE odoo",
        'odoo_install_smoke"',
        "odoo install",
        "not_the_smoke_db",
    ],
)
def test_unrecognized_or_protected_database_never_calls_docker(tmp_path: Path, name: str) -> None:
    proc = _run(tmp_path, {"ODOO_INSTALL_SMOKE_DB": name})
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "install-smoke refused" in output
    assert _docker_log(tmp_path) == ""


def test_remote_docker_host_never_calls_docker(tmp_path: Path) -> None:
    proc = _run(tmp_path, {"DOCKER_HOST": "tcp://203.0.113.10:2375"})
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "remote Docker endpoint" in output
    assert _docker_log(tmp_path) == ""


def test_foreign_compose_project_never_calls_docker(tmp_path: Path) -> None:
    proc = _run(tmp_path, {"ODOO_COMPOSE_PROJECT": "production-odoo"})
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "not this repo's disposable stack" in output
    assert _docker_log(tmp_path) == ""


def test_compose_mode_rejects_a_remote_database_host(tmp_path: Path) -> None:
    proc = _run(tmp_path, {"ODOO_DB_HOST": "db.internal.example", "ODOO_INSTALL_SMOKE_NETWORK": "compose"})
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "not the local db service" in output
    assert _docker_log(tmp_path) == ""


def test_foreign_compose_file_never_calls_docker(tmp_path: Path) -> None:
    other = tmp_path / "other-compose.yml"
    other.write_text("name: elsewhere\nservices:\n  db:\n    image: postgres\n", encoding="utf-8")
    proc = _run(tmp_path, {"COMPOSE_FILE": str(other)})
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "COMPOSE_FILE" in output
    assert _docker_log(tmp_path) == ""


def test_host_mode_without_a_proven_container_does_not_mutate(tmp_path: Path) -> None:
    proc = _run(
        tmp_path,
        {"ODOO_INSTALL_SMOKE_NETWORK": "host", "ODOO_DB_HOST": "127.0.0.1", "ODOO_DB_PORT": "5433"},
        container_id="",
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "host mode is blocked" in output
    log = _docker_log(tmp_path)
    assert "ps -q db" in log
    _assert_no_destructive(log)


def test_host_mode_rejects_a_non_loopback_port_binding(tmp_path: Path) -> None:
    root = str(ROOT)
    inspect = f"""[{{
      "Config": {{"Labels": {{
        "com.docker.compose.project": "odoo19",
        "com.docker.compose.service": "db",
        "com.docker.compose.project.working_dir": "{root}"
      }}}},
      "HostConfig": {{"PortBindings": {{"5432/tcp": [{{"HostIp": "0.0.0.0", "HostPort": "5433"}}]}}}}
    }}]"""
    proc = _run(
        tmp_path,
        {"ODOO_INSTALL_SMOKE_NETWORK": "host"},
        inspect_json=inspect,
        container_id="abc123",
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    log = _docker_log(tmp_path)
    assert "inspect abc123" in log
    _assert_no_destructive(log)


def test_default_compose_identity_reaches_the_scratch_install(tmp_path: Path) -> None:
    proc = _run(tmp_path, {})
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    log = _docker_log(tmp_path)
    assert "DROP DATABASE IF EXISTS" in log
    assert "odoo_install_smoke" in log
    assert "pg_terminate_backend" in log
    assert "build odoo-test" in log
    assert "--stop-after-init" in log
    assert 'DROP DATABASE IF EXISTS \\"odoo\\"' not in log
    assert "datname = 'odoo'" not in log
    drop_at = log.index("DROP DATABASE")
    assert log.index("build odoo-test") < drop_at


def test_proven_host_endpoint_reaches_the_scratch_install(tmp_path: Path) -> None:
    root = str(ROOT)
    inspect = f"""[{{
      "Config": {{"Labels": {{
        "com.docker.compose.project": "odoo19",
        "com.docker.compose.service": "db",
        "com.docker.compose.project.working_dir": "{root}"
      }}}},
      "HostConfig": {{"PortBindings": {{"5432/tcp": [{{"HostIp": "127.0.0.1", "HostPort": "5433"}}]}}}}
    }}]"""
    proc = _run(
        tmp_path,
        {"ODOO_INSTALL_SMOKE_NETWORK": "host"},
        inspect_json=inspect,
        container_id="abc123",
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    log = _docker_log(tmp_path)
    assert log.index("inspect abc123") < log.index("DROP DATABASE")
    assert "DROP DATABASE IF EXISTS" in log and "odoo_install_smoke" in log
    assert "--stop-after-init" in log


def test_cache_hit_is_not_described_as_install_proof() -> None:
    text = (ROOT / "scripts" / "pr_check_run.sh").read_text(encoding="utf-8")
    assert "cache hit is not environment-specific install proof" in text

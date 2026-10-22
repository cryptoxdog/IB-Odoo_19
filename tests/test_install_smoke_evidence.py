"""Adversarial installation-evidence contracts: real shell/Git/files/locks, fake Docker.

Docker is an external boundary, not the oracle. The real installer resolves,
byte-hashes, locks, writes and rechecks its own receipt. Every rejection test
first establishes a valid passing control. No Enterprise source or daemon is
needed. PLASTICOS_SMOKE_SOURCE is for offline calibration of a pinned donor;
it is not read by production code and is forbidden in the required CI tier.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.adversarial_contract

# Deliberately small synthetic addons; these are not copies of licensed addons.
CUSTOM = "plasticos_base,plasticos_product"
ENTERPRISE = "account_accountant,web_enterprise"

# Strict command-boundary fake: it never computes a fingerprint, decides reuse,
# acquires a lock, or writes evidence. Unknown commands are errors, not success.
DOCKER_FAKE = r"""#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
control = Path(os.environ["FAKE_DOCKER_CONTROL"])
c = json.loads(control.read_text())
state_path = control.with_name("database.json")
log = control.with_name("docker.jsonl")
with log.open("a") as out:
    out.write(json.dumps({"cwd": os.getcwd(), "args": args}) + "\n")
def state():
    return json.loads(state_path.read_text()) if state_path.exists() else {}
def save(value):
    tmp = state_path.with_suffix("." + str(os.getpid()) + ".tmp")
    tmp.write_text(json.dumps(value)); tmp.replace(state_path)
def image(ref):
    return c.get("images", {}).get(ref, c.get("image_id", "sha256:image"))
if args[:2] == ["context", "inspect"]:
    print(c.get("context_host", "unix:///var/run/docker.sock")); sys.exit(0)
if args[:1] == ["info"]:
    print(c.get("daemon", "fixture-daemon")); sys.exit(0)
if args[:2] == ["image", "inspect"]:
    print(image(args[-1])); sys.exit(0)
if args[:1] == ["inspect"]:
    if args[-1] == "fixture-db-container":
        print(c.get("postgres_image", "sha256:pg"))
    else:
        print(state().get("containers", {}).get(args[-1], ""))
    sys.exit(0)
if args[:1] == ["rm"]:
    sys.exit(0)
if args[:1] == ["run"] and "xmlsec" in " ".join(args):
    print("xmlsec fixture"); sys.exit(0)
if args[:1] != ["compose"]:
    raise SystemExit("unexpected Docker call: " + repr(args))
args = args[3:]  # compose -p PROJECT
if args[:1] == ["config"]:
    if "--format" not in args:
        print("  db:\n    POSTGRES_PASSWORD: fixture"); sys.exit(0)
    root = Path.cwd()
    enterprise = Path(os.environ.get("ODOO_ENTERPRISE_PATH", str(root / "odoo-enterprise"))).resolve()
    service = {"build": {"context": str(root)}, "volumes": [
        {"type": "bind", "source": str(root), "target": "/mnt/extra-addons"},
        {"type": "bind", "source": str(enterprise), "target": "/mnt/enterprise", "read_only": True},
        {"type": "bind", "source": str(root / "config"), "target": "/etc/odoo", "read_only": True}],
        "environment": {"L9_REQUIRE_SIGNATURE": os.environ.get("L9_REQUIRE_SIGNATURE", ""),
                        "L9_SIGNING_KEY": os.environ.get("L9_SIGNING_KEY", "fixture-only-not-a-secret")}}
    if c.get("image_ref"):
        service["image"] = c["image_ref"]
    print(json.dumps({"name": "odoo19", "services": {"odoo-test": service}})); sys.exit(0)
if args[:1] == ["ps"]:
    print("fixture-db-container" if "-q" in args else "db running"); sys.exit(0)
if args[:1] == ["up"]:
    sys.exit(0)
if args[:1] == ["build"]:
    if c.get("built_image_id"):
        c["image_id"] = c["built_image_id"]
        control.write_text(json.dumps(c))
    sys.exit(0)
def quoted(text, after):
    return text.split(after, 1)[1].split('"', 2)[1]
def databases(st):
    return st.setdefault("databases", {})
if args[:1] == ["exec"]:
    query = args[-1]
    target = args[args.index("-d") + 1] if "-d" in args else "postgres"
    if "pg_isready" in args: sys.exit(0)
    if "pg_terminate_backend" in query: sys.exit(0)
    if "server_version_num" in query:
        print(c.get("postgres_major", "15")); sys.exit(0)
    if "DROP DATABASE" in query:
        st = state(); databases(st).pop(quoted(query, "DROP DATABASE IF EXISTS "), None); save(st); sys.exit(0)
    if "CREATE DATABASE" in query:
        st = state(); name = quoted(query, "CREATE DATABASE "); template = quoted(query, "TEMPLATE ")
        if template not in databases(st) or name in databases(st): sys.exit(1)
        st["next_oid"] = st.get("next_oid", 16384) + 1
        databases(st)[name] = {"oid": str(st["next_oid"]), "modules": dict(databases(st)[template]["modules"]), "comment": ""}
        save(st); sys.exit(0)
    if "COMMENT ON DATABASE" in query:
        st = state(); name = quoted(query, "COMMENT ON DATABASE ")
        if name not in databases(st): sys.exit(1)
        databases(st)[name]["comment"] = query.split(" IS '", 1)[1].rsplit("'", 1)[0]; save(st); sys.exit(0)
    if "RENAME TO" in query:
        st = state(); old = quoted(query, "ALTER DATABASE "); new = quoted(query, "RENAME TO ")
        if old not in databases(st) or new in databases(st): sys.exit(1)
        databases(st)[new] = databases(st).pop(old); save(st); sys.exit(0)
    if "FROM pg_database" in query:
        name = query.split("datname = '", 1)[1].split("'", 1)[0]
        entry = databases(state()).get(name)
        if "shobj_description" in query:
            print(entry["comment"] if entry else "")
        else:
            print(entry["oid"] if entry else "")
        sys.exit(0)
    if "SELECT name || '=' || state" in query:
        if c.get("database_missing"): sys.exit(1)
        entry = databases(state()).get(target)
        if entry is None: sys.exit(1)
        for name, value in entry["modules"].items(): print(name + "=" + value)
        sys.exit(0)
    if "SELECT state FROM ir_module_module" in query:
        name = query.split("name = '", 1)[1].split("'", 1)[0]
        entry = databases(state()).get(target) or {"modules": {}}
        print(entry["modules"].get(name, "")); sys.exit(0)
if args[:1] == ["run"]:
    if "xmlsec" in " ".join(args): print("xmlsec fixture"); sys.exit(0)
    if "-i" not in args: raise SystemExit("unexpected non-install compose run")
    current = state()
    name = args[args.index("--name") + 1] if "--name" in args else "unnamed"
    current.setdefault("containers", {})[name] = c.get("executed_image", image(c.get("image_ref", "odoo19-odoo-test:latest")))
    save(current)
    if os.environ.get("FAKE_WAIT") == "1":
        control.with_name("started").touch()
        end = time.monotonic() + 15
        while not control.with_name("release").exists():
            if time.monotonic() > end: raise SystemExit("fixture release timed out")
            time.sleep(0.02)
    if c.get("mutate_file"):
        Path(c["mutate_file"]).write_text("changed during install\n")
    if c.get("install_failure"): sys.exit(7)
    current = state()
    target = args[args.index("-d") + 1]
    entry = databases(current).get(target)
    if entry is None:  # odoo -i -d creates a missing database: a new OID
        current["next_oid"] = current.get("next_oid", 16384) + 1
        entry = databases(current)[target] = {"oid": str(current["next_oid"]), "modules": {}, "comment": ""}
    entry["modules"].update({name: "installed" for name in args[args.index("-i") + 1].split(",")})
    for name in c.get("missing_modules", []): entry["modules"].pop(name, None)
    save(current); print("registry initialized (fixture only)"); sys.exit(0)
raise SystemExit("unexpected Docker call: " + repr(args))
"""


def _smoke_installs(site: Site) -> list[dict]:
    """Odoo installs into the disposable smoke database (base builds target another database)."""
    return [
        call
        for call in site.calls()
        if "-i" in call["args"]
        and "-d" in call["args"]
        and call["args"][call["args"].index("-d") + 1] == "odoo_install_smoke"
    ]


def _base_builds(site: Site) -> list[dict]:
    return [
        call
        for call in site.calls()
        if "-i" in call["args"]
        and "-d" in call["args"]
        and call["args"][call["args"].index("-d") + 1].startswith("odoo_install_smoke_base")
    ]


@dataclass
class Site:
    root: Path
    control: Path
    env: dict[str, str]

    @property
    def receipt(self) -> Path:
        return self.root / ".cache/pr-check/install-smoke.sha"

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "scripts/install_smoke.sh", *args],
            cwd=self.root,
            env={**self.env, **env},
            text=True,
            capture_output=True,
            timeout=25,
            check=False,
        )

    def configure(self, **values: object) -> None:
        data = json.loads(self.control.read_text())
        data.update(values)
        self.control.write_text(json.dumps(data))

    def calls(self) -> list[dict]:
        path = self.control.with_name("docker.jsonl")
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def establish(self, **env: str) -> dict:
        result = self.run(**env)
        assert result.returncode == 0, result.stdout + result.stderr
        assert self.receipt.is_file(), "A successful full installation must write its own evidence"
        result = self.run("--recheck", **env)
        assert result.returncode == 0, "Unchanged, complete evidence must be reusable: " + result.stdout + result.stderr
        return json.loads(self.receipt.read_text())


def _git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )


def _addons(root: Path) -> None:
    """Synthetic PlasticOS addons with every file class the load surface distinguishes."""
    for name in CUSTOM.split(","):
        addon = root / name
        for sub in ("models", "data", "security", "tests", "i18n", "static/src", "erp_extracted_data"):
            (addon / sub).mkdir(parents=True)
        (addon / "__manifest__.py").write_text(
            "{'name': 'fixture', 'installable': True, 'depends': ['base'],\n"
            " 'data': ['security/ir.model.access.csv', 'data/seed.xml'], 'demo': ['data/demo.xml']}\n"
        )
        (addon / "__init__.py").write_text("from . import models\n")
        (addon / "models/__init__.py").write_text("from . import model\n")
        (addon / "models/model.py").write_text("VALUE = 'A'\n")
        (addon / "data/seed.xml").write_text("<odoo noupdate='1'><data/></odoo>\n")
        (addon / "data/demo.xml").write_text("<odoo><data/></odoo>\n")
        (addon / "security/ir.model.access.csv").write_text("id,name\n")
        (addon / "tests/__init__.py").write_text("")
        (addon / "tests/test_model.py").write_text("def test_model():\n    assert True\n")
        (addon / "i18n/fr.po").write_text('msgid "A"\nmsgstr "A"\n')
        (addon / "static/src/widget.js").write_text("export const value = 'A';\n")
        (addon / "README.md").write_text("# fixture\n")
        (addon / "erp_extracted_data/grid.csv").write_text("id,value\n1,A\n")


def _checkout(path: Path, *, git: bool = False) -> Path:
    for name in ENTERPRISE.split(","):
        (path / name).mkdir(parents=True)
        (path / name / "__manifest__.py").write_text("{'name': 'fixture', 'installable': True}\n")
    (path / "payload.py").write_text("VALUE = 'A'\n")
    if git:
        _git(path, "init")
        _git(path, "add", ".")
        _git(path, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "fixture")
    return path


@pytest.fixture
def site(tmp_path: Path) -> Site:
    root = tmp_path / "worktree-a"
    (root / "scripts").mkdir(parents=True)
    (root / "ci").mkdir()
    (root / "config").mkdir()
    source = Path(os.environ.get("PLASTICOS_SMOKE_SOURCE", ROOT / "scripts/install_smoke.sh"))
    shutil.copyfile(source, root / "scripts/install_smoke.sh")
    # The load-surface owner is part of the installer under test, never a stub.
    shutil.copyfile(ROOT / "scripts/odoo_load_surface.py", root / "scripts/odoo_load_surface.py")
    _addons(root)
    (root / "scripts/get_odoo_module_order.py").write_text(
        f"import sys\nprint({ENTERPRISE!r} if '--section' in sys.argv else "
        f"({CUSTOM!r} if '--all-installable' in sys.argv else 'plasticos_base'))\n"
    )
    (root / "ci/check_xml_module_ref_deps.py").write_text("raise SystemExit(0)\n")
    (root / "config/odoo.conf").write_text("[options]\nworkers = 0\n")
    (root / "docker-compose.yml").write_text(
        "name: odoo19\nservices:\n  db:\n    image: postgres:15\n    environment:\n"
        '      POSTGRES_DB: odoo\n    ports:\n      - "5433:5432"\n'
    )
    enterprise = _checkout(tmp_path / "enterprise-a")
    (root / "odoo-enterprise").symlink_to(enterprise)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # Installer Python snippets and the Docker fake use stdlib only. Avoid
    # inheriting site startup instrumentation/coverage into these subprocesses.
    python = bindir / "python3"
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" -S "$@"\n')
    python.chmod(0o755)
    docker = bindir / "docker"
    docker.write_text(DOCKER_FAKE)
    docker.chmod(0o755)
    control = tmp_path / "control.json"
    control.write_text("{}")
    home = tmp_path / "home"
    home.mkdir()
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(
            (
                "COV_CORE_",
                "COVERAGE_",
                "ODOO_",
                "POSTGRES_",
                "L9_",
                "COMPOSE_",
                "DOCKER_",
                "PR_CHECK_",
                "INSTALL_SMOKE_",
                "PYTEST_",
                "PLASTICOS_",
            )
        )
    }
    env.update(
        {
            "PATH": str(bindir) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            "HOME": str(home),
            "POSTGRES_PASSWORD": "fixture-password-not-a-secret",
            "FAKE_DOCKER_CONTROL": str(control),
            "SMOKE_LOCK_WAIT": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return Site(root, control, env)


def test_remote_active_docker_context_cannot_touch_the_database(site: Site) -> None:
    site.configure(context_host="ssh://ops@remote.example")
    result = site.run()
    assert result.returncode == 2, "DOCKER_CONTEXT: remote endpoint was accepted: " + result.stdout + result.stderr
    assert "Docker context endpoint" in result.stdout + result.stderr
    assert not any("DROP DATABASE" in " ".join(call["args"]) for call in site.calls())


def test_unchanged_complete_evidence_is_reused_without_install(site: Site) -> None:
    site.establish()
    before = len(_smoke_installs(site))
    for _ in range(2):
        result = site.run("--recheck")
        assert result.returncode == 0, result.stderr
    assert len(_smoke_installs(site)) == before == 1
    assert len(_base_builds(site)) == 1


def test_effective_enterprise_mount_not_repository_symlink_is_bound(site: Site, tmp_path: Path) -> None:
    other = _checkout(tmp_path / "enterprise-b")
    record = site.establish(ODOO_ENTERPRISE_PATH=str(other))
    assert record["enterprise_realpath"] == str(other), "EE_SOURCE: receipt must describe Docker's actual mount"
    (other / "payload.py").write_text("VALUE = 'B'\n")
    result = site.run("--recheck", ODOO_ENTERPRISE_PATH=str(other))
    assert result.returncode != 0, "EE_SOURCE: changed mounted checkout was accepted"


def test_same_length_bytes_with_preserved_mtime_invalidate(site: Site) -> None:
    site.establish()
    path = site.root / "odoo-enterprise/payload.py"
    before = path.stat()
    path.write_text("VALUE = 'B'\n")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    result = site.run("--recheck")
    assert result.returncode != 0, "EE_BYTES: metadata-equivalent different bytes were accepted"


def test_untracked_git_file_content_not_just_status_is_bound(site: Site) -> None:
    enterprise = (site.root / "odoo-enterprise").resolve()
    _git(enterprise, "init")
    _git(enterprise, "add", ".")
    _git(enterprise, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "fixture")
    path = enterprise / "untracked.py"
    path.write_text("VALUE = 'A'\n")
    site.establish()
    before = subprocess.check_output(["git", "-C", str(enterprise), "status", "--porcelain"])
    path.write_text("VALUE = 'B'\n")
    assert subprocess.check_output(["git", "-C", str(enterprise), "status", "--porcelain"]) == before
    assert site.run("--recheck").returncode != 0, "EE_UNTRACKED: changed bytes hidden by unchanged Git status"


@pytest.mark.parametrize(
    "env",
    [
        {"L9_REQUIRE_SIGNATURE": "true"},
        {"L9_SIGNING_KEY": "different-fixture-secret"},
    ],
)
def test_effective_container_environment_is_bound(site: Site, env: dict[str, str]) -> None:
    site.establish()
    assert site.run("--recheck", **env).returncode != 0, "CONFIG: different effective runtime settings accepted"


def test_mounted_configuration_file_is_bound(site: Site) -> None:
    site.establish()
    (site.root / "config/odoo.conf").write_text("[options]\nworkers = 2\n")
    assert site.run("--recheck").returncode != 0, "CONFIG_FILE: mounted Odoo configuration change was ignored"


def test_image_override_cannot_attest_to_an_unexecuted_image(site: Site) -> None:
    result = site.run(ODOO_SMOKE_IMAGE="unrelated:latest")
    assert result.returncode != 0, "IMAGE_BINDING: unused image override was certified"
    assert not any("DROP DATABASE" in " ".join(c["args"]) for c in site.calls())


def test_actual_container_image_must_match_validated_image(site: Site) -> None:
    site.configure(executed_image="sha256:different-container")
    result = site.run()
    assert result.returncode != 0, "IMAGE_EXECUTION: installation ran a different image but evidence was issued"
    assert not site.receipt.exists()


def test_legitimate_build_image_change_is_accepted(site: Site) -> None:
    site.configure(built_image_id="sha256:new-build")
    record = site.establish()
    assert record["image_id"] == "sha256:new-build"


@pytest.mark.parametrize(
    "change",
    [{"image_id": "sha256:other"}, {"postgres_image": "sha256:other-pg"}, {"database_missing": True}],
)
def test_live_image_and_database_change_invalidates(site: Site, change: dict) -> None:
    site.establish()
    site.configure(**change)
    assert site.run("--recheck").returncode != 0, "LIVE_STATE: changed live evidence accepted"


@pytest.mark.parametrize("module", ("account_accountant", "plasticos_base"))
def test_missing_enterprise_or_custom_module_never_passes(site: Site, module: str) -> None:
    site.establish()
    db = site.control.with_name("database.json")
    data = json.loads(db.read_text())
    data["modules"].pop(module)
    db.write_text(json.dumps(data))
    assert site.run("--recheck").returncode != 0


def test_truncated_record_cannot_reduce_required_inventory(site: Site) -> None:
    record = site.establish()
    record["states"].pop("account_accountant")
    site.receipt.write_text(json.dumps(record))
    assert site.run("--recheck").returncode != 0, "INVENTORY: incomplete evidence was treated as full parity"


@pytest.mark.parametrize("value", ["not-json", "[]", "{}", "a" * 64])
def test_malformed_or_old_hash_evidence_is_not_reusable(site: Site, value: str) -> None:
    site.establish()
    site.receipt.write_text(value)
    assert site.run("--recheck").returncode != 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("ODOO_ENTERPRISE_MODULES", "none"),
        ("ODOO_ENTERPRISE_MODULES", "account_accountant"),
        ("ODOO_INSTALL_SMOKE_SCOPE", "ordered"),
        ("ODOO_REBUILD_MODULES", "plasticos_base"),
    ],
)
def test_shortened_lists_refuse_from_shell_and_dotenv(site: Site, key: str, value: str) -> None:
    assert site.run("--resolve").returncode == 0
    assert site.run("--resolve", **{key: value}).returncode != 0
    (site.root / ".env").write_text(f"{key}={value}\n")
    assert site.run("--resolve").returncode != 0
    assert not site.calls(), "--resolve is filesystem/config only, not a Docker execution"


def test_unreadable_enterprise_fails_resolve(site: Site) -> None:
    (site.root / "odoo-enterprise").unlink()
    result = site.run("--resolve")
    assert result.returncode != 0
    assert not site.calls()


def test_source_change_during_install_never_writes_evidence(site: Site) -> None:
    site.configure(mutate_file=str(site.root / "odoo-enterprise/payload.py"))
    result = site.run()
    assert result.returncode != 0
    assert not site.receipt.exists(), "INSTALL_SNAPSHOT: changed installation inputs received evidence"


def test_failed_install_invalidates_old_success(site: Site) -> None:
    site.establish()
    site.configure(install_failure=True)
    result = site.run()
    assert result.returncode != 0
    assert not site.receipt.exists(), "FAILED_INSTALL: old successful evidence survived a failed replacement"


def test_manual_reduced_install_cannot_refresh_publication_evidence(site: Site) -> None:
    site.establish()
    result = site.run(ODOO_ENTERPRISE_MODULES="none")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not site.receipt.exists(), "MANUAL_SCOPE: reduced install retained publication evidence"
    assert site.run("--recheck").returncode != 0


def test_receipt_contains_no_configuration_secret_values(site: Site) -> None:
    secret = "private-fixture-value-not-a-real-secret"
    site.establish(L9_SIGNING_KEY=secret)
    assert secret not in site.receipt.read_text()


def test_two_real_worktrees_share_the_database_lock(site: Site, tmp_path: Path) -> None:
    # Both agents share HOME and the daemon/database but have different Git roots.
    _git(site.root, "init")
    (site.root / ".gitignore").write_text(".cache/\nodoo-enterprise\n")
    _git(site.root, "add", ".")
    _git(site.root, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "fixture")
    other = tmp_path / "worktree-b"
    _git(site.root, "worktree", "add", "--detach", str(other))
    (other / "odoo-enterprise").symlink_to((site.root / "odoo-enterprise").resolve())
    second = Site(other, site.control, site.env)
    first = subprocess.Popen(
        ["bash", "scripts/install_smoke.sh"],
        cwd=site.root,
        env={**site.env, "FAKE_WAIT": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        end = time.monotonic() + 12
        while not site.control.with_name("started").exists():
            assert first.poll() is None, first.communicate()
            assert time.monotonic() < end, "first installer never acquired its lock and started"
            time.sleep(0.02)
        result = second.run()
        assert result.returncode == 2, (
            "LOCK_DOMAIN: second worktree entered the shared destructive operation: " + result.stdout + result.stderr
        )
        assert "lock busy" in result.stdout + result.stderr
        drops = [
            call for call in site.calls() if 'DROP DATABASE IF EXISTS "odoo_install_smoke"' in " ".join(call["args"])
        ]
        assert len(drops) == 1, "LOCK_DOMAIN: two worktrees dropped the same database"
    finally:
        site.control.with_name("release").touch()
        try:
            first.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            first.kill()
            first.communicate()


def test_another_worktree_reinstall_invalidates_the_receipt(site: Site, tmp_path: Path) -> None:
    # Same daemon, database and image ID; different source. The image cannot tell
    # the installs apart, so the receipt must bind the database instance itself.
    site.establish()
    other_root = tmp_path / "worktree-b"
    shutil.copytree(site.root, other_root, symlinks=True, ignore=shutil.ignore_patterns(".cache"))
    (other_root / "plasticos_base" / "models" / "model.py").write_text("VALUE = 'B'\n")
    other = Site(other_root, site.control, site.env)
    other.establish()
    result = site.run("--recheck")
    assert result.returncode != 0, "SHARED_DB: another worktree's reinstall left this receipt valid"
    assert "database_oid changed" in result.stdout + result.stderr


def test_enterprise_checkout_with_unavailable_gitdir_is_still_byte_bound(site: Site) -> None:
    enterprise = (site.root / "odoo-enterprise").resolve()
    (enterprise / ".git").write_text("gitdir: /nonexistent/worktrees/enterprise\n")
    site.establish()
    (enterprise / "payload.py").write_text("VALUE = 'B'\n")
    assert site.run("--recheck").returncode != 0, "EE_GITDIR: unreadable gitdir hid a source change"


@pytest.mark.parametrize("mutation", ["version_2", "version_3", "no_database_oid"])
def test_receipt_without_database_binding_is_not_reusable(site: Site, mutation: str) -> None:
    record = site.establish()
    if mutation == "version_2":
        record["evidence_version"] = 2
    elif mutation == "version_3":
        # v3 hashed every byte under plasticos_*/; a v3 receipt never proves the v4 load surface.
        record["evidence_version"] = 3
    else:
        record.pop("database_oid")
    site.receipt.write_text(json.dumps(record))
    assert site.run("--recheck").returncode != 0


# --- Load surface (evidence v4): only what odoo-bin reads at install invalidates evidence ---


@pytest.mark.parametrize(
    "rel",
    [
        "plasticos_base/README.md",
        "plasticos_base/erp_extracted_data/grid.csv",
        "plasticos_base/tests/test_model.py",
        "plasticos_base/data/demo.xml",
    ],
)
def test_non_load_file_change_under_addon_keeps_evidence(site: Site, rel: str) -> None:
    site.establish()
    before = len(_smoke_installs(site))
    (site.root / rel).write_text("changed\n")
    result = site.run("--recheck")
    assert result.returncode == 0, (
        "LOAD_SURFACE: a non-load file invalidated evidence: " + result.stdout + result.stderr
    )
    assert len(_smoke_installs(site)) == before == 1


@pytest.mark.parametrize(
    "rel",
    [
        "plasticos_base/__manifest__.py",
        "plasticos_base/models/model.py",
        "plasticos_base/data/seed.xml",
        "plasticos_base/security/ir.model.access.csv",
        "plasticos_base/i18n/fr.po",
        "plasticos_base/static/src/widget.js",
        "config/odoo.conf",
        "docker-compose.yml",
        "scripts/get_odoo_module_order.py",
    ],
)
def test_load_surface_change_invalidates(site: Site, rel: str) -> None:
    site.establish()
    path = site.root / rel
    path.write_text(path.read_text() + "\n# changed\n")
    result = site.run("--recheck")
    assert result.returncode != 0, "LOAD_SURFACE: a load input change was accepted: " + rel


def test_untracked_python_under_addon_invalidates(site: Site) -> None:
    site.establish()
    (site.root / "plasticos_base/models/untracked.py").write_text("VALUE = 'B'\n")
    assert site.run("--recheck").returncode != 0, "LOAD_SURFACE: a new untracked .py under an addon was accepted"


def test_manifest_declared_file_missing_refuses_resolve_and_recheck(site: Site) -> None:
    site.establish()
    (site.root / "plasticos_base/data/seed.xml").unlink()
    assert site.run("--resolve").returncode != 0, "LOAD_SURFACE: a missing declared data file passed --resolve"
    assert site.run("--recheck").returncode != 0, "LOAD_SURFACE: a missing declared data file kept evidence"


def test_receipt_declares_evidence_version_4(site: Site) -> None:
    record = site.establish()
    assert record["evidence_version"] == 4


# --- Enterprise base template: installed once per (image, Enterprise tree, list, PostgreSQL major) ---


def test_first_install_builds_the_base_then_installs_only_custom_modules(site: Site) -> None:
    record = site.establish()
    builds = _base_builds(site)
    assert len(builds) == 1
    assert builds[0]["args"][builds[0]["args"].index("-i") + 1] == ENTERPRISE
    smoke = _smoke_installs(site)
    assert len(smoke) == 1
    assert smoke[0]["args"][smoke[0]["args"].index("-i") + 1] == CUSTOM, "BASE: the smoke install re-installed the base"
    clones = [c for c in site.calls() if 'TEMPLATE "odoo_install_smoke_base"' in " ".join(c["args"])]
    assert len(clones) == 1, "BASE: the smoke database was not cloned from the base"
    assert record["base_fp"] and record["base_oid"], "BASE: the receipt does not bind the base template"
    assert record["states"] == {name: "installed" for name in (ENTERPRISE + "," + CUSTOM).split(",")}


def test_base_is_reused_when_only_custom_inputs_change(site: Site) -> None:
    site.establish()
    (site.root / "plasticos_base/models/model.py").write_text("VALUE = 'B'\n")
    assert site.run("--recheck").returncode != 0
    result = site.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_base_builds(site)) == 1, "BASE: a custom change rebuilt the Enterprise base"
    assert len(_smoke_installs(site)) == 2
    assert "reusing it" in result.stdout


@pytest.mark.parametrize(
    "change",
    [
        ("image", {"image_id": "sha256:other-build"}),
        ("postgres", {"postgres_major": "16"}),
        ("enterprise", None),
    ],
)
def test_base_is_rebuilt_when_its_inputs_change(site: Site, change: tuple[str, dict | None]) -> None:
    first = site.establish()
    kind, values = change
    if values is None:
        (site.root / "odoo-enterprise/payload.py").write_text("VALUE = 'B'\n")
    else:
        site.configure(**values)
    result = site.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_base_builds(site)) == 2, "BASE: changed base inputs did not rebuild the Enterprise base: " + kind
    second = json.loads(site.receipt.read_text())
    assert second["base_fp"] != first["base_fp"]


def test_receipt_bound_to_a_base_that_disappears_is_not_reusable(site: Site) -> None:
    site.establish()
    state_path = site.control.with_name("database.json")
    state = json.loads(state_path.read_text())
    state["databases"].pop("odoo_install_smoke_base")
    state_path.write_text(json.dumps(state))
    result = site.run("--recheck")
    assert result.returncode != 0, "BASE: evidence survived the loss of its base template"
    assert "base template changed" in result.stdout + result.stderr


def test_base_with_a_foreign_or_missing_stamp_is_rebuilt_not_trusted(site: Site) -> None:
    site.establish()
    state_path = site.control.with_name("database.json")
    state = json.loads(state_path.read_text())
    state["databases"]["odoo_install_smoke_base"]["comment"] = "plasticos-smoke-base fp=deadbeef state=ready"
    state_path.write_text(json.dumps(state))
    (site.root / "plasticos_base/models/model.py").write_text("VALUE = 'B'\n")
    result = site.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_base_builds(site)) == 2, "BASE: a base with a foreign stamp was reused"


def test_legacy_full_install_switch_installs_everything_in_one_run(site: Site) -> None:
    record = site.establish(ODOO_INSTALL_SMOKE_BASE="0")
    assert _base_builds(site) == []
    smoke = _smoke_installs(site)
    assert len(smoke) == 1
    assert smoke[0]["args"][smoke[0]["args"].index("-i") + 1] == ENTERPRISE + "," + CUSTOM
    assert record["base_fp"] == "" and record["base_oid"] == ""
    assert site.run("--recheck", ODOO_INSTALL_SMOKE_BASE="0").returncode == 0
    assert site.run("--recheck").returncode != 0, "BASE: a legacy receipt satisfied a base-mode recheck"


def test_failed_base_build_writes_no_evidence_and_no_base(site: Site) -> None:
    site.configure(install_failure=True)
    result = site.run()
    assert result.returncode != 0
    assert not site.receipt.exists()
    state_path = site.control.with_name("database.json")
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    assert "odoo_install_smoke_base" not in state.get("databases", {}), "BASE: a failed build was published as ready"

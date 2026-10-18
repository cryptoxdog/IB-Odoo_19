"""Publication refuses before any remote mutation unless Staging and live L4 agree.

Git push, gh, make, and the L4 interpreter are stubs. Nothing here contacts GitHub.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = "scripts/make_push_pipeline.sh"
PUSH = "scripts/git_push_with_pr.sh"


def _real(name: str) -> str:
    found = shutil.which(name)
    assert found, name
    return found


REAL_GIT = _real("git")
REAL_PYTHON = _real("python3")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _plant_l4_provider(tmp_path: Path) -> None:
    """Fixture governance tree. CI runners have no ~/.cursor-governance."""
    gov = tmp_path / "gov-home" / ".cursor-governance"
    scripts = gov / "ops" / "scripts"
    autonomy = gov / "ops" / "autonomy"
    scripts.mkdir(parents=True)
    autonomy.mkdir(parents=True)
    (autonomy / "l4_local.py").write_text("# fixture provider\n", encoding="utf-8")
    gov_root = str(gov.resolve())
    _write(
        scripts / "resolve_governance_paths.sh",
        f'#!/bin/bash\nresolve_governance_paths() {{\n  GOV_ROOT="{gov_root}"\n  return 0\n}}\n',
    )


def _init_repo(tmp_path: Path, branch: str = "fix/example") -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    _plant_l4_provider(tmp_path)
    seq = tmp_path / "seq.log"
    subprocess.run([REAL_GIT, "init", "-b", branch], cwd=repo, check=True, capture_output=True)
    scripts = repo / "scripts"
    scripts.mkdir()
    for name in ("make_push_pipeline.sh", "git_push_with_pr.sh", "git_open_pr.sh"):
        shutil.copy(ROOT / "scripts" / name, scripts / name)
    _write(
        scripts / "install_smoke.sh",
        f"""#!/bin/bash
echo "smoke $*" >> "{seq}"
exit "${{INSTALL_SMOKE_RC:-0}}"
""",
    )
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run([REAL_GIT, "add", "scripts", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [REAL_GIT, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [REAL_GIT, "remote", "add", "origin", "https://github.com/cryptoxdog/IB-Odoo_19.git"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _write(
        bindir / "git",
        f"""#!/bin/bash
if [[ "$1" == "push" ]]; then
  echo "push" >> "{seq}"
  exit 0
fi
if [[ "$1" == "ls-remote" ]]; then
  echo "ls-remote" >> "{seq}"
  if [[ -n "${{REMOTE_SHA:-}}" ]]; then
    printf '%s\\n' "$REMOTE_SHA"
  else
    "{REAL_GIT}" rev-parse HEAD
  fi
  exit 0
fi
exec "{REAL_GIT}" "$@"
""",
    )
    _write(
        bindir / "python3",
        f"""#!/bin/bash
joined="$*"
if [[ "$joined" == *l4_local.py* ]]; then
  echo "l4 $joined" >> "{seq}"
  count="$(grep -c '^l4 ' "{seq}" || true)"
  if [[ -n "${{L4_FAIL_CALL:-}}" && "$count" == "$L4_FAIL_CALL" ]]; then
    echo '{{"allowed": false, "reason": "stale"}}'
    exit 2
  fi
  if [[ "${{L4_RC:-0}}" != "0" ]]; then
    echo '{{"allowed": false, "reason": "denied"}}'
    exit "$L4_RC"
  fi
  echo '{{"allowed": true, "reason": "test-receipt"}}'
  exit 0
fi
exec "{REAL_PYTHON}" "$@"
""",
    )
    _write(
        bindir / "make",
        f"""#!/bin/bash
echo "make PR_CHECK_FORCE_SMOKE=${{PR_CHECK_FORCE_SMOKE-}}" >> "{seq}"
if [[ "${{MAKE_DIRTY:-0}}" == "1" ]]; then
  echo dirty >> "$PWD/dirty.txt"
fi
exit 0
""",
    )
    _write(
        bindir / "gitleaks",
        f"""#!/bin/bash
echo "gitleaks $*" >> "{seq}"
exit "${{GITLEAKS_RC:-0}}"
""",
    )
    _write(
        bindir / "gh",
        f"""#!/bin/bash
echo "gh $1 ${{2:-}}" >> "{seq}"
if [[ "$1" == "auth" ]]; then
  exit "${{GH_AUTH_RC:-0}}"
fi
if [[ "$1" == "pr" && "$2" == "list" ]]; then
  if [[ "${{GH_LIST_RC:-0}}" != "0" ]]; then
    exit "$GH_LIST_RC"
  fi
  printf '%s\\n' "${{GH_PR_JSON:-}}"
  exit 0
fi
exit 0
""",
    )
    return repo, seq


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("COV_CORE_", "COVERAGE_"))}
    env.pop("L9_L4_LOCAL_AUTONOMY", None)
    env.pop("L9_LOCAL_PUSH_AUTHORIZED", None)
    env["PATH"] = f"{tmp_path / 'bin'}{os.pathsep}/bin{os.pathsep}/usr/bin"
    if "HOME" not in extra:
        env["HOME"] = str(tmp_path / "gov-home")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env.update(extra)
    return env


def _run(repo: Path, tmp_path: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", PIPELINE, "", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path, **extra),
        timeout=30,
    )


def _seq(seq: Path) -> str:
    return seq.read_text(encoding="utf-8") if seq.exists() else ""


def _assert_no_push(seq: Path) -> None:
    assert "\npush\n" not in f"\n{_seq(seq)}\n"


def _pr_json(repo: Path, branch: str) -> str:
    sha = subprocess.check_output([REAL_GIT, "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    return json.dumps(
        {
            "number": 222,
            "url": "https://github.com/cryptoxdog/IB-Odoo_19/pull/222",
            "state": "OPEN",
            "baseRefName": "Staging",
            "headRefName": branch,
            "headRefOid": sha,
        }
    )


def test_feature_to_staging_publishes_only_after_l4_and_forced_smoke(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", GH_PR_JSON=_pr_json(repo, "fix/example"))
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    text = _seq(seq)
    assert "make PR_CHECK_FORCE_SMOKE=1" not in text
    assert "make PR_CHECK_FORCE_SMOKE=\n" in text or "make PR_CHECK_FORCE_SMOKE=\r\n" in text
    worktree = os.path.realpath(repo)
    governance = os.path.realpath(os.path.expanduser("~/.cursor-governance"))
    workspaces = [line.split("--workspace", 1)[1].strip() for line in text.splitlines() if line.startswith("l4 ")]
    assert workspaces == [worktree, worktree]
    assert governance not in workspaces
    assert text.index("l4 ") < text.rindex("l4 ") < text.index("gitleaks ")
    assert text.index("gitleaks ") < text.index("smoke --resolve") < text.index("make ")
    assert text.index("make ") < text.index("smoke --recheck") < text.index("\npush\n")
    assert "Open PR #222" in output


def test_production_base_refuses_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _run(repo, tmp_path, "fix/example", "Production", "1", "0")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "destination must be Staging" in output
    _assert_no_push(seq)


def test_staging_to_production_refuses_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path, branch="Staging")
    proc = _run(repo, tmp_path, "Staging", "Production", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "destination must be Staging" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def test_protected_sources_refuse_before_push(tmp_path: Path) -> None:
    for branch in ("Staging", "Production"):
        repo, seq = _init_repo(tmp_path / branch, branch=branch)
        proc = _run(repo, tmp_path / branch, branch, "Staging", "1", "0")
        output = proc.stdout + proc.stderr
        assert proc.returncode == 1, output
        assert "protected source" in output or "self-PR" in output
        _assert_no_push(seq)


def test_self_pr_and_detached_head_refuse_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "self", branch="Staging")
    proc = _run(repo, tmp_path / "self", "Staging", "Staging", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    _assert_no_push(seq)

    detached, detached_seq = _init_repo(tmp_path / "detached")
    subprocess.run([REAL_GIT, "checkout", "--detach"], cwd=detached, check=True, capture_output=True)
    proc = _run(detached, tmp_path / "detached", "fix/example", "Staging", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "detached HEAD" in (proc.stdout + proc.stderr)
    _assert_no_push(detached_seq)


def test_dirty_tree_refuses_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "not clean" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def test_l4_denial_and_second_check_failure_do_not_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "deny")
    denied = _run(repo, tmp_path / "deny", "fix/example", "Staging", "1", "0", L4_RC="2")
    assert denied.returncode == 1, denied.stdout + denied.stderr
    assert "denied release" in (denied.stdout + denied.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "second")
    second = _run(repo2, tmp_path / "second", "fix/example", "Staging", "1", "0", L4_FAIL_CALL="2")
    output = second.stdout + second.stderr
    assert second.returncode == 1, output
    assert "make " not in _seq(seq2)
    _assert_no_push(seq2)


def test_disable_and_breakglass_switches_do_not_invoke_l4_or_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "off")
    off = _run(repo, tmp_path / "off", "fix/example", "Staging", "1", "0", L9_L4_LOCAL_AUTONOMY="0")
    assert off.returncode == 1, off.stdout + off.stderr
    assert "not release authorization" in (off.stdout + off.stderr)
    assert not _seq(seq).startswith("l4 ")
    assert "l4 " not in _seq(seq)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "glass")
    glass = _run(repo2, tmp_path / "glass", "fix/example", "Staging", "1", "0", L9_LOCAL_PUSH_AUTHORIZED="yes")
    assert glass.returncode == 1, glass.stdout + glass.stderr
    assert "L9_LOCAL_PUSH_AUTHORIZED" in (glass.stdout + glass.stderr)
    assert "l4 " not in _seq(seq2)
    _assert_no_push(seq2)


def test_missing_provider_blocks_without_a_dropbox_fallback(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    proc = _run(repo, tmp_path, "fix/example", "Staging", "1", "0", HOME=str(home))
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "L4 provider is not available" in output
    _assert_no_push(seq)
    script = (ROOT / "scripts" / "git_push_with_pr.sh").read_text(encoding="utf-8")
    assert "Dropbox" not in script
    assert "check-remote" in script
    assert "--workspace" in script


def test_missing_gh_auth_and_pr_lookup_refuse_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "nogh")
    bindir = tmp_path / "nogh" / "bin"
    bindir.joinpath("gh").unlink()
    # Ubuntu merges /bin and /usr/bin, so a PATH that contains /bin still finds gh.
    bindir.joinpath("bash").symlink_to(_real("bash"))
    bindir.joinpath("tr").symlink_to(_real("tr"))
    missing = _run(
        repo,
        tmp_path / "nogh",
        "fix/example",
        "Staging",
        "1",
        "0",
        PATH=str(bindir),
    )
    assert missing.returncode == 1, missing.stdout + missing.stderr
    assert "gh CLI is not available" in (missing.stdout + missing.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "auth")
    unauth = _run(repo2, tmp_path / "auth", "fix/example", "Staging", "1", "0", GH_AUTH_RC="1")
    assert unauth.returncode == 1
    assert "not authenticated" in (unauth.stdout + unauth.stderr)
    _assert_no_push(seq2)

    repo3, seq3 = _init_repo(tmp_path / "list")
    lookup = _run(repo3, tmp_path / "list", "fix/example", "Staging", "1", "0", GH_LIST_RC="1")
    assert lookup.returncode == 1
    assert "cannot look up pull requests" in (lookup.stdout + lookup.stderr)
    _assert_no_push(seq3)


def test_remote_sha_mismatch_fails_the_push_proof(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _run(
        repo,
        tmp_path,
        "fix/example",
        "Staging",
        "1",
        "0",
        GH_PR_JSON=_pr_json(repo, "fix/example"),
        REMOTE_SHA="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" in output
    assert "gh pr create" not in _seq(seq)


def test_direct_push_to_a_protected_branch_refuses(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = subprocess.run(
        ["bash", PUSH, "Production"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "protected branch" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def test_open_pr_refuses_a_non_staging_base(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = subprocess.run(
        ["bash", "scripts/git_open_pr.sh", "fix/example", "Production"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "destination must be Staging" in (proc.stdout + proc.stderr)
    assert _seq(seq) == ""


def test_pr_check_reuses_live_evidence_not_a_source_hash() -> None:
    text = (ROOT / "scripts" / "pr_check_run.sh").read_text(encoding="utf-8")
    assert "smoke_fingerprint" not in text
    assert "--recheck" in text
    assert "install-smoke.sha" not in text


def test_api_push_and_autopilot_do_not_publish() -> None:
    proc = subprocess.run(
        [REAL_PYTHON, str(ROOT / "scripts" / "api_push.py")], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 1
    assert "only publication ceremony is make pr" in proc.stdout
    sys.path.insert(0, str(ROOT / "scripts"))
    from pr_autopilot import atomic_push

    assert atomic_push("fix/example", "fix: local only") is False


def _push(repo: Path, tmp_path: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", PUSH, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path, **extra),
        timeout=30,
    )


def test_direct_push_runs_the_gates_before_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _push(repo, tmp_path, "fix/example")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = _seq(seq)
    assert text.index("gitleaks ") < text.index("smoke --resolve") < text.index("make ")
    assert text.index("make ") < text.index("smoke --recheck") < text.index("\npush\n")


def test_failed_or_missing_gitleaks_does_not_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "fail")
    failed = _push(repo, tmp_path / "fail", "fix/example", GITLEAKS_RC="2")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "gitleaks detect failed" in (failed.stdout + failed.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "missing")
    (tmp_path / "missing" / "bin" / "gitleaks").unlink()
    missing = _push(repo2, tmp_path / "missing", "fix/example")
    assert missing.returncode == 1, missing.stdout + missing.stderr
    assert "gitleaks is not on PATH" in (missing.stdout + missing.stderr)
    _assert_no_push(seq2)


def test_hook_exit_does_not_replace_the_gitleaks_result(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    _write(hooks / "pre-push", "#!/bin/bash\nexit 1\n")
    subprocess.run([REAL_GIT, "config", "core.hooksPath", str(hooks)], cwd=repo, check=True)
    script = (repo / "scripts" / "git_push_with_pr.sh").read_text(encoding="utf-8")
    assert "git push --no-verify" in script
    blocked = _push(repo, tmp_path, "fix/example", GITLEAKS_RC="2")
    assert blocked.returncode == 1
    _assert_no_push(seq)
    allowed = _push(repo, tmp_path, "fix/example", GITLEAKS_RC="0")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "\npush\n" in f"\n{_seq(seq)}\n"


def test_bad_origin_and_skip_switches_refuse(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path / "url")
    subprocess.run(
        [REAL_GIT, "remote", "set-url", "--push", "origin", "https://github.com/cryptoxdog/IB-Odoo_19.git"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        [REAL_GIT, "remote", "set-url", "--add", "--push", "origin", "https://github.com/other/repo.git"],
        cwd=repo,
        check=True,
    )
    multi = _push(repo, tmp_path / "url", "fix/example")
    assert multi.returncode == 1, multi.stdout + multi.stderr
    assert "exactly one push URL" in (multi.stdout + multi.stderr)
    _assert_no_push(seq)

    repo2, seq2 = _init_repo(tmp_path / "foreign")
    subprocess.run(
        [REAL_GIT, "remote", "set-url", "origin", "https://github.com/other/repo.git"],
        cwd=repo2,
        check=True,
    )
    foreign = _push(repo2, tmp_path / "foreign", "fix/example")
    assert foreign.returncode == 1
    assert "not cryptoxdog/IB-Odoo_19" in (foreign.stdout + foreign.stderr)
    _assert_no_push(seq2)

    repo3, seq3 = _init_repo(tmp_path / "skip")
    skipped = _push(repo3, tmp_path / "skip", "fix/example", PR_CHECK_SKIP_SMOKE="1")
    assert skipped.returncode == 1
    assert "PR_CHECK_SKIP_SMOKE" in (skipped.stdout + skipped.stderr)
    _assert_no_push(seq3)


def test_worktree_change_after_validation_does_not_push(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    proc = _push(repo, tmp_path, "fix/example", MAKE_DIRTY="1")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "changed during validation" in (proc.stdout + proc.stderr)
    _assert_no_push(seq)


def test_reused_pr_keeps_its_body_and_gains_the_stamp(tmp_path: Path) -> None:
    repo, seq = _init_repo(tmp_path)
    body_file = tmp_path / "body.txt"
    body_file.write_text("Human notes stay.\n", encoding="utf-8")
    _write(
        tmp_path / "bin" / "gh",
        f"""#!/bin/bash
echo "gh $*" >> "{seq}"
if [[ "$1" == "auth" ]]; then exit 0; fi
if [[ "$1" == "pr" && "$2" == "view" ]]; then
  cat "{body_file}"
  exit 0
fi
if [[ "$1" == "pr" && "$2" == "edit" ]]; then
  next=""
  prev=""
  for arg in "$@"; do
    if [[ "$prev" == "--body" ]]; then next="$arg"; fi
    prev="$arg"
  done
  printf '%s' "$next" > "{body_file}"
  exit 0
fi
if [[ "$1" == "pr" && "$2" == "list" ]]; then
  printf '%s\\n' '{json.dumps({"number": 7, "url": "https://example.test/7", "state": "OPEN", "baseRefName": "Staging", "headRefName": "fix/example", "headRefOid": "HEADSHA"})}'
  exit 0
fi
exit 0
""",
    )
    sha = subprocess.check_output([REAL_GIT, "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    listed = body_file.read_text(encoding="utf-8")
    del listed
    gh = (tmp_path / "bin" / "gh").read_text(encoding="utf-8").replace("HEADSHA", sha)
    (tmp_path / "bin" / "gh").write_text(gh, encoding="utf-8")
    proc = subprocess.run(
        ["bash", "scripts/git_open_pr.sh", "fix/example", "Staging"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    saved = body_file.read_text(encoding="utf-8")
    assert saved.startswith("Human notes stay.")
    assert saved.count("<!-- L9_PROTECTED_ROOT_PR -->") == 1
    again = subprocess.run(
        ["bash", "scripts/git_open_pr.sh", "fix/example", "Staging"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_env(tmp_path),
        timeout=30,
    )
    assert again.returncode == 0, again.stdout + again.stderr
    assert body_file.read_text(encoding="utf-8").count("<!-- L9_PROTECTED_ROOT_PR -->") == 1


def test_real_gitleaks_rejects_a_seeded_secret(tmp_path: Path) -> None:
    repo = tmp_path / "scan"
    repo.mkdir()
    shutil.copy(ROOT / ".gitleaks.toml", repo / ".gitleaks.toml")
    token = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
    (repo / "secret.txt").write_text(f"token={token}\n", encoding="utf-8")
    proc = subprocess.run(
        ["gitleaks", "detect", "--config", ".gitleaks.toml", "--redact", "--exit-code", "2", "--no-git"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr


def _order_script() -> str:
    return (
        "import sys\n"
        "if '--all-installable' in sys.argv:\n"
        "    print('plasticos_base,plasticos_product')\n"
        "elif '--section' in sys.argv:\n"
        "    print('account_accountant,web_enterprise')\n"
        "else:\n"
        "    print('plasticos_base')\n"
    )


def _smoke_tree(tmp_path: Path) -> Path:
    repo = tmp_path / "smoke"
    (repo / "scripts").mkdir(parents=True)
    (repo / "ci").mkdir()
    shutil.copy(ROOT / "scripts" / "install_smoke.sh", repo / "scripts" / "install_smoke.sh")
    (repo / "scripts" / "get_odoo_module_order.py").write_text(_order_script(), encoding="utf-8")
    (repo / "ci" / "check_xml_module_ref_deps.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (repo / "docker-compose.yml").write_text(
        "name: odoo19\nservices:\n  db:\n    image: postgres:15\n    environment:\n"
        '      POSTGRES_DB: odoo\n    ports:\n      - "5433:5432"\n',
        encoding="utf-8",
    )
    enterprise = repo / "enterprise-src"
    enterprise.mkdir()
    subprocess.run([REAL_GIT, "init"], cwd=enterprise, check=True, capture_output=True)
    (enterprise / "README").write_text("ee\n", encoding="utf-8")
    subprocess.run([REAL_GIT, "add", "README"], cwd=enterprise, check=True, capture_output=True)
    subprocess.run(
        [REAL_GIT, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "ee"],
        cwd=enterprise,
        check=True,
        capture_output=True,
    )
    (repo / "odoo-enterprise").symlink_to(enterprise)
    return repo


def _smoke_env(tmp_path: Path, repo: Path) -> dict[str, str]:
    bindir = tmp_path / "docker-bin"
    bindir.mkdir(exist_ok=True)
    log = tmp_path / "docker.log"
    _write(
        bindir / "docker",
        f"""#!/bin/bash
printf '%s\\n' "$*" >> "{log}"
if [[ "$*" == *"DROP DATABASE"* ]]; then
  echo DROP >> "{log}"
fi
if [[ "$1" == "image" && "$2" == "inspect" ]]; then
  printf '%s\\n' "${{DOCKER_IMAGE_ID:-sha256:image}}"
  exit 0
fi
if [[ "$1" == "inspect" ]]; then
  printf '%s\\n' "${{DOCKER_PG_IMAGE:-sha256:pg}}"
  exit 0
fi
if [[ "$1" == "compose" && "$*" == *"ps -q db"* ]]; then
  printf '%s\\n' "cid"
  exit 0
fi
if [[ "$1" == "compose" && "$*" == *"pg_isready"* ]]; then
  exit 0
fi
if [[ "$1" == "compose" && "$*" == *"ir_module_module"* ]]; then
  printf '%s\\n' "${{DOCKER_STATES:-installed}}"
  exit 0
fi
exit 0
""",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}{Path(REAL_PYTHON).parent}{os.pathsep}/usr/bin{os.pathsep}/bin"
    env["HOME"] = str(tmp_path / "home")
    env["POSTGRES_PASSWORD"] = "odoo"
    env["SMOKE_LOCK_WAIT"] = "1"
    Path(env["HOME"]).mkdir(exist_ok=True)
    env.pop("ODOO_ENTERPRISE_MODULES", None)
    env.pop("ODOO_REBUILD_MODULES", None)
    env.pop("ODOO_INSTALL_SMOKE_SCOPE", None)
    env.pop("ODOO_ENTERPRISE_PATH", None)
    return env


def _run_smoke(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/install_smoke.sh", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )


def test_resolve_rejects_shortened_lists_including_dotenv(tmp_path: Path) -> None:
    repo = _smoke_tree(tmp_path)
    env = _smoke_env(tmp_path, repo)
    ok = _run_smoke(repo, env, "--resolve")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "account_accountant,web_enterprise" in ok.stdout

    for key, value in (
        ("ODOO_ENTERPRISE_MODULES", "none"),
        ("ODOO_ENTERPRISE_MODULES", "account_accountant"),
        ("ODOO_INSTALL_SMOKE_SCOPE", "ordered"),
        ("ODOO_REBUILD_MODULES", "plasticos_base"),
    ):
        refused = _run_smoke(repo, {**env, key: value}, "--resolve")
        assert refused.returncode == 1, (key, refused.stdout + refused.stderr)

    (repo / ".env").write_text("ODOO_ENTERPRISE_MODULES=account_accountant\n", encoding="utf-8")
    from_file = _run_smoke(repo, env, "--resolve")
    assert from_file.returncode == 1, from_file.stdout + from_file.stderr
    assert "not the full canonical" in (from_file.stdout + from_file.stderr)


def test_resolve_refuses_an_unreadable_enterprise_checkout(tmp_path: Path) -> None:
    repo = _smoke_tree(tmp_path)
    (repo / "odoo-enterprise").unlink()
    env = _smoke_env(tmp_path, repo)
    proc = _run_smoke(repo, env, "--resolve")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "not readable" in (proc.stdout + proc.stderr)


def test_recheck_misses_when_evidence_or_image_or_database_changed(tmp_path: Path) -> None:
    repo = _smoke_tree(tmp_path)
    env = _smoke_env(tmp_path, repo)
    absent = _run_smoke(repo, env, "--recheck")
    assert absent.returncode == 1
    assert "evidence is absent" in (absent.stdout + absent.stderr)

    snapshot = _run_smoke(repo, env, "--print-snapshot")
    assert snapshot.returncode == 0, snapshot.stdout + snapshot.stderr
    record = {
        "snapshot": snapshot.stdout.strip(),
        "image_id": "sha256:image",
        "postgres_image_id": "sha256:pg",
        "database": "odoo_install_smoke",
        "states": {"plasticos_base": "installed", "account_accountant": "installed"},
    }
    evidence = repo / ".cache" / "pr-check" / "install-smoke.sha"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(record), encoding="utf-8")

    changed_image = _run_smoke(repo, {**env, "DOCKER_IMAGE_ID": "sha256:other"}, "--recheck")
    assert changed_image.returncode == 1
    assert "odoo image changed" in (changed_image.stdout + changed_image.stderr)

    (enterprise_readme := repo / "enterprise-src" / "README").write_text("changed\n", encoding="utf-8")
    changed_tree = _run_smoke(repo, env, "--recheck")
    assert changed_tree.returncode == 1
    assert "inputs changed" in (changed_tree.stdout + changed_tree.stderr)
    enterprise_readme.write_text("ee\n", encoding="utf-8")

    missing_db = _run_smoke(repo, {**env, "DOCKER_STATES": ""}, "--recheck")
    assert missing_db.returncode == 1
    assert "missing" in (missing_db.stdout + missing_db.stderr)

    evidence.write_text(snapshot.stdout.strip() + "\n", encoding="utf-8")
    stale_hash = _run_smoke(repo, env, "--recheck")
    assert stale_hash.returncode != 0


def test_snapshot_change_during_install_does_not_write_evidence(tmp_path: Path) -> None:
    repo = _smoke_tree(tmp_path)
    env = _smoke_env(tmp_path, repo)
    env["INSTALL_SMOKE_SNAPSHOT_BREAK"] = "1"
    proc = _run_smoke(repo, env)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "inputs changed during install" in (proc.stdout + proc.stderr)
    assert not (repo / ".cache" / "pr-check" / "install-smoke.sha").exists()


def test_second_install_does_not_drop_while_the_lock_is_held(tmp_path: Path) -> None:
    repo = _smoke_tree(tmp_path)
    env = _smoke_env(tmp_path, repo)
    lock = repo / ".cache" / "pr-check" / "install-smoke.odoo19.odoo_install_smoke.lock"
    lock.parent.mkdir(parents=True)
    holder = subprocess.Popen(
        [
            REAL_PYTHON,
            "-c",
            "import fcntl,os,time,sys; fd=os.open(sys.argv[1], os.O_CREAT|os.O_RDWR); "
            "fcntl.flock(fd, fcntl.LOCK_EX); time.sleep(5)",
            str(lock),
        ]
    )
    time.sleep(0.3)
    try:
        proc = _run_smoke(repo, env)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "lock busy" in (proc.stdout + proc.stderr)
        log = (tmp_path / "docker.log").read_text(encoding="utf-8") if (tmp_path / "docker.log").exists() else ""
        assert "DROP" not in log
    finally:
        holder.kill()
        holder.wait(timeout=5)

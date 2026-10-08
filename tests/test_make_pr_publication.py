"""Publication refuses before any remote mutation unless Staging and live L4 agree.

Git push, gh, make, and the L4 interpreter are stubs. Nothing here contacts GitHub.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run([REAL_GIT, "add", "scripts", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [REAL_GIT, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
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
exit 0
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
    assert "make PR_CHECK_FORCE_SMOKE=1" in text
    worktree = os.path.realpath(repo)
    governance = os.path.realpath(os.path.expanduser("~/.cursor-governance"))
    workspaces = [line.split("--workspace", 1)[1].strip() for line in text.splitlines() if line.startswith("l4 ")]
    assert workspaces == [worktree, worktree]
    assert governance not in workspaces
    assert text.index("l4 ") < text.index("make ") < text.rindex("l4 ") < text.index("\npush\n")
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
    assert "make PR_CHECK_FORCE_SMOKE=1" in _seq(seq2)
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
    # tr is required before the gh probe. On Ubuntu, gh and tr share /usr/bin.
    bindir.joinpath("tr").symlink_to(_real("tr"))
    missing = _run(
        repo,
        tmp_path / "nogh",
        "fix/example",
        "Staging",
        "1",
        "0",
        PATH=f"{bindir}{os.pathsep}/bin",
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


def test_api_push_and_autopilot_do_not_publish() -> None:
    proc = subprocess.run(
        [REAL_PYTHON, str(ROOT / "scripts" / "api_push.py")], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 1
    assert "only publication ceremony is make pr" in proc.stdout
    sys.path.insert(0, str(ROOT / "scripts"))
    from pr_autopilot import atomic_push

    assert atomic_push("fix/example", "fix: local only") is False

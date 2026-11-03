"""Real git + real pre-commit: what the pre-push stage does and does not see.

These tests characterize the hook runner the publication gate depends on. A
pre-commit release that changes any of these behaviours fails here before it
can change what `make pr` or a direct `git push` validates.

Exception (95-test-fix-policy): the module skips when no `pre-commit` binary is
on PATH. CI's pure-python job installs pytest only (ci.yml is out of scope for
this change), and the behaviour under test is the real runner's, so a stub
would assert nothing. Removal trigger: pre-commit added to that job's install
line. The same pattern guards the real-gitleaks test in
tests/test_make_pr_publication.py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRE_COMMIT = shutil.which("pre-commit")
GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(
    PRE_COMMIT is None or GIT is None, reason="pre-commit or git is not installed in this job"
)

PROBE = """\
import json, os, sys
keys = ("PRE_COMMIT_FROM_REF", "PRE_COMMIT_TO_REF", "PRE_COMMIT_REMOTE_NAME",
        "PRE_COMMIT_REMOTE_BRANCH", "PRE_COMMIT_LOCAL_BRANCH")
with open(os.environ["PROBE_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({k: os.environ.get(k) for k in keys}) + "\\n")
"""

PROBE_CONFIG = """\
repos:
  - repo: local
    hooks:
      - id: probe
        name: probe
        entry: python3 probe.py
        language: system
        stages: [pre-push]
        pass_filenames: false
        always_run: true
"""


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PRE_COMMIT_", "GIT_"))}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
        PRE_COMMIT_HOME=str(tmp_path / "pre-commit-home"),
        PROBE_LOG=str(tmp_path / "probe.jsonl"),
    )
    env.pop("SKIP", None)
    env.update(extra)
    return env


def _git(repo: Path, env: dict[str, str], *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    assert GIT
    return subprocess.run([GIT, *args], cwd=repo, env=env, capture_output=True, text=True, check=check, timeout=60)


def _commit(repo: Path, env: dict[str, str], name: str) -> str:
    (repo / f"{name}.txt").write_text(f"{name}\n", encoding="utf-8")
    _git(repo, env, "add", f"{name}.txt")
    _git(repo, env, "commit", "-q", "-m", name)
    return _git(repo, env, "rev-parse", "HEAD").stdout.strip()


def _probe_repo(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """Work repo with a pre-commit-installed pre-push probe and a local bare origin."""
    env = _env(tmp_path)
    repo = tmp_path / "work"
    bare = tmp_path / "origin.git"
    repo.mkdir()
    subprocess.run([GIT, "init", "-q", "--bare", str(bare)], env=env, check=True)
    _git(repo, env, "init", "-q", "-b", "main")
    (repo / ".pre-commit-config.yaml").write_text(PROBE_CONFIG, encoding="utf-8")
    (repo / "probe.py").write_text(PROBE, encoding="utf-8")
    _git(repo, env, "add", ".pre-commit-config.yaml", "probe.py")
    _git(repo, env, "commit", "-q", "-m", "init")
    _git(repo, env, "remote", "add", "origin", str(bare))
    assert PRE_COMMIT
    subprocess.run(
        [PRE_COMMIT, "install", "--hook-type", "pre-push"], cwd=repo, env=env, check=True, capture_output=True
    )
    return repo, bare, env


def _log(tmp_path: Path) -> list[dict[str, str | None]]:
    path = tmp_path / "probe.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _clear(tmp_path: Path) -> None:
    (tmp_path / "probe.jsonl").unlink(missing_ok=True)


def _remote_ref(bare: Path, env: dict[str, str], ref: str) -> str:
    proc = subprocess.run(
        [GIT, "--git-dir", str(bare), "rev-parse", "--verify", "--quiet", ref],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def test_root_history_push_runs_in_all_files_mode_without_refs(tmp_path: Path) -> None:
    repo, bare, env = _probe_repo(tmp_path)
    _git(repo, env, "push", "-q", "origin", "main")
    [entry] = _log(tmp_path)
    assert entry["PRE_COMMIT_TO_REF"] is None and entry["PRE_COMMIT_FROM_REF"] is None
    assert entry["PRE_COMMIT_REMOTE_NAME"] == "origin"
    assert entry["PRE_COMMIT_REMOTE_BRANCH"] == "refs/heads/main"


def test_update_push_exports_the_full_pushed_sha(tmp_path: Path) -> None:
    repo, bare, env = _probe_repo(tmp_path)
    _git(repo, env, "push", "-q", "origin", "main")
    first = _git(repo, env, "rev-parse", "HEAD").stdout.strip()
    second = _commit(repo, env, "second")
    _clear(tmp_path)
    _git(repo, env, "push", "-q", "origin", f"{second}:refs/heads/feature")
    [entry] = _log(tmp_path)
    assert entry["PRE_COMMIT_TO_REF"] == second
    assert entry["PRE_COMMIT_FROM_REF"] == first
    assert entry["PRE_COMMIT_REMOTE_NAME"] == "origin"
    assert entry["PRE_COMMIT_REMOTE_BRANCH"] == "refs/heads/feature"


def test_re_pushing_a_published_sha_runs_no_hook(tmp_path: Path) -> None:
    """F1: a retry where git has nothing new to push never reaches the pre-push stage."""
    repo, bare, env = _probe_repo(tmp_path)
    _git(repo, env, "push", "-q", "origin", "main")
    sha = _commit(repo, env, "second")
    _git(repo, env, "push", "-q", "origin", f"{sha}:refs/heads/feature")
    _clear(tmp_path)
    proc = _git(repo, env, "push", "origin", f"{sha}:refs/heads/feature")
    assert proc.returncode == 0
    assert _log(tmp_path) == [], "the pre-push stage ran on an up-to-date push"


def test_git_invokes_pre_push_with_no_refs_on_an_up_to_date_push_and_pre_commit_runs_nothing(
    tmp_path: Path,
) -> None:
    """Git calls the hook for an up-to-date push but sends no ref lines on stdin.

    pre-commit therefore finds nothing to push and runs no configured hook. The
    pre-push stage cannot be the only owner of the publication gate.
    """
    repo, bare, env = _probe_repo(tmp_path)
    _git(repo, env, "push", "-q", "origin", "main")
    sha = _git(repo, env, "rev-parse", "HEAD").stdout.strip()
    raw_log = tmp_path / "raw.log"
    hook = repo / ".git" / "hooks" / "pre-push"
    generated = hook.read_text(encoding="utf-8")
    hook.write_text(f'#!/usr/bin/env bash\necho "raw $*" >> "{raw_log}"\ncat >> "{raw_log}"\n', encoding="utf-8")
    hook.chmod(0o755)
    _git(repo, env, "push", "-q", "origin", f"{sha}:refs/heads/main")
    raw = raw_log.read_text(encoding="utf-8") if raw_log.exists() else ""
    hook.write_text(generated, encoding="utf-8")
    _clear(tmp_path)
    _git(repo, env, "push", "-q", "origin", f"{sha}:refs/heads/main")
    assert raw.startswith("raw origin "), raw
    assert raw.count("\n") == 1, f"git sent ref lines for an up-to-date push: {raw!r}"
    assert _log(tmp_path) == []


def test_new_ref_to_an_already_remote_commit_runs_no_hook_but_creates_the_ref(tmp_path: Path) -> None:
    repo, bare, env = _probe_repo(tmp_path)
    _git(repo, env, "push", "-q", "origin", "main")
    sha = _git(repo, env, "rev-parse", "HEAD").stdout.strip()
    _clear(tmp_path)
    _git(repo, env, "push", "-q", "origin", f"{sha}:refs/heads/alias")
    assert _log(tmp_path) == [], "pre-commit ran hooks for a ref with no new commits"
    assert _remote_ref(bare, env, "refs/heads/alias") == sha


def test_multi_ref_push_validates_only_the_first_new_ref(tmp_path: Path) -> None:
    repo, bare, env = _probe_repo(tmp_path)
    _git(repo, env, "push", "-q", "origin", "main")
    one = _commit(repo, env, "one")
    _git(repo, env, "reset", "-q", "--hard", "HEAD~1")
    two = _commit(repo, env, "two")
    _clear(tmp_path)
    _git(repo, env, "push", "-q", "origin", f"{one}:refs/heads/one", f"{two}:refs/heads/two")
    entries = _log(tmp_path)
    assert len(entries) == 1, entries
    assert entries[0]["PRE_COMMIT_TO_REF"] in {one, two}
    assert _remote_ref(bare, env, "refs/heads/one") == one
    assert _remote_ref(bare, env, "refs/heads/two") == two


def test_synthetic_run_forwards_a_literal_to_ref(tmp_path: Path) -> None:
    """F7: `pre-commit run --to-ref HEAD` hands hooks the literal string, not a SHA."""
    repo, bare, env = _probe_repo(tmp_path)
    assert PRE_COMMIT
    subprocess.run(
        [PRE_COMMIT, "run", "--hook-stage", "pre-push", "--from-ref", "HEAD", "--to-ref", "HEAD"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
    )
    [entry] = _log(tmp_path)
    assert entry["PRE_COMMIT_TO_REF"] == "HEAD"


# --- the revised pre-push stage, under real git and real pre-commit ----------

GATE_HOOK_IDS = ("gitleaks-push", "pr-validate")


def _gate_hooks() -> list[dict]:
    """gitleaks-push and pr-validate exactly as .pre-commit-config.yaml declares them."""
    yaml = pytest.importorskip("yaml")
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}
    pre_push = [
        hook["id"]
        for repo in config["repos"]
        for hook in repo["hooks"]
        if "pre-push" in (hook.get("stages") or config.get("default_stages") or ["pre-push"])
    ]
    assert pre_push[-2:] == list(GATE_HOOK_IDS), pre_push
    return [hooks[hook_id] for hook_id in GATE_HOOK_IDS]


def _gate_repo(tmp_path: Path) -> tuple[Path, Path, dict[str, str], Path]:
    """Work repo whose pre-push stage is the real gate hooks, with stub make/gitleaks."""
    yaml = pytest.importorskip("yaml")
    seq = tmp_path / "seq.log"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in (("make", "MAKE_RC"), ("gitleaks", "GITLEAKS_RC")):
        stub = bindir / name
        stub.write_text(f'#!/bin/bash\necho "{name} $*" >> "{seq}"\nexit "${{{body}:-0}}"\n', encoding="utf-8")
        stub.chmod(0o755)
    env = _env(tmp_path, PATH=f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}")
    repo = tmp_path / "work"
    bare = tmp_path / "origin.git"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "pre_push_validate.sh", repo / "scripts" / "pre_push_validate.sh")
    config = {"default_stages": ["pre-commit"], "repos": [{"repo": "local", "hooks": _gate_hooks()}]}
    (repo / ".pre-commit-config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    subprocess.run([GIT, "init", "-q", "--bare", str(bare)], env=env, check=True)
    _git(repo, env, "init", "-q", "-b", "fix/example")
    _git(repo, env, "add", ".")
    _git(repo, env, "commit", "-q", "-m", "init")
    _git(repo, env, "remote", "add", "origin", str(bare))
    # Seed the remote without a push, so the next push is an ordinary update.
    subprocess.run(
        [GIT, "--git-dir", str(bare), "fetch", "-q", str(repo), "fix/example:refs/heads/fix/example"],
        env=env,
        check=True,
    )
    assert PRE_COMMIT
    subprocess.run(
        [PRE_COMMIT, "install", "--hook-type", "pre-push"], cwd=repo, env=env, check=True, capture_output=True
    )
    _commit(repo, env, "next")
    return repo, bare, env, seq


def _gate_seq(seq: Path) -> list[str]:
    return seq.read_text(encoding="utf-8").splitlines() if seq.exists() else []


def _push_head(repo: Path, env: dict[str, str], **extra: str) -> subprocess.CompletedProcess[str]:
    return _git(repo, {**env, **extra}, "push", "origin", "HEAD:refs/heads/fix/example", check=False)


def test_direct_push_runs_gitleaks_then_pr_check_and_publishes(tmp_path: Path) -> None:
    repo, bare, env, seq = _gate_repo(tmp_path)
    head = _git(repo, env, "rev-parse", "HEAD").stdout.strip()
    proc = _push_head(repo, env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _gate_seq(seq) == ["gitleaks detect --config .gitleaks.toml --redact --exit-code 2", "make pr-check"]
    assert _remote_ref(bare, env, "refs/heads/fix/example") == head


def test_direct_push_with_failing_pr_check_leaves_the_remote_unchanged(tmp_path: Path) -> None:
    repo, bare, env, seq = _gate_repo(tmp_path)
    before = _remote_ref(bare, env, "refs/heads/fix/example")
    proc = _push_head(repo, env, MAKE_RC="2")
    assert proc.returncode != 0
    assert "make pr-check failed" in proc.stdout + proc.stderr
    assert _remote_ref(bare, env, "refs/heads/fix/example") == before


def test_gitleaks_finding_stops_the_stage_before_pr_check(tmp_path: Path) -> None:
    repo, bare, env, seq = _gate_repo(tmp_path)
    before = _remote_ref(bare, env, "refs/heads/fix/example")
    proc = _push_head(repo, env, GITLEAKS_RC="2")
    assert proc.returncode != 0
    assert _gate_seq(seq) == ["gitleaks detect --config .gitleaks.toml --redact --exit-code 2"], "fail_fast"
    assert _remote_ref(bare, env, "refs/heads/fix/example") == before


def test_publisher_bound_push_skips_both_heavy_hooks(tmp_path: Path) -> None:
    repo, bare, env, seq = _gate_repo(tmp_path)
    head = _git(repo, env, "rev-parse", "HEAD").stdout.strip()
    proc = _push_head(repo, env, L9_PUBLISH_VALIDATED_SHA=head, L9_PUBLISH_TARGET="fix/example")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _gate_seq(seq) == []
    assert _remote_ref(bare, env, "refs/heads/fix/example") == head


def test_binding_for_another_branch_still_runs_the_gate(tmp_path: Path) -> None:
    repo, bare, env, seq = _gate_repo(tmp_path)
    head = _git(repo, env, "rev-parse", "HEAD").stdout.strip()
    proc = _push_head(repo, env, L9_PUBLISH_VALIDATED_SHA=head, L9_PUBLISH_TARGET="fix/other")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _gate_seq(seq) == ["gitleaks detect --config .gitleaks.toml --redact --exit-code 2", "make pr-check"]

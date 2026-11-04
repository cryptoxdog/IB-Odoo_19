"""scripts/pre_push_validate.sh: the pre-push gate a direct push depends on.

The script runs as a pre-commit hook; here it is driven with the environment
pre-commit gives it, and with stub `make` and `gitleaks` that log each call.
Nothing here needs pre-commit, so the suite runs in every CI job.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pre_push_validate.sh"
GIT = shutil.which("git")
BASH = shutil.which("bash")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def work(tmp_path: Path) -> tuple[Path, Path, str]:
    assert GIT and BASH
    repo = tmp_path / "repo"
    repo.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    seq = tmp_path / "seq.log"
    env = _base_env(tmp_path)
    subprocess.run([GIT, "init", "-q", "-b", "fix/example"], cwd=repo, env=env, check=True)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".cache/\n", encoding="utf-8")
    subprocess.run([GIT, "add", "README.md", ".gitignore"], cwd=repo, env=env, check=True)
    subprocess.run([GIT, "commit", "-q", "-m", "init"], cwd=repo, env=env, check=True)
    _write(
        bindir / "make",
        f"""#!/bin/bash
echo "make $*" >> "{seq}"
if [[ "${{MAKE_MOVES_HEAD:-0}}" == "1" ]]; then
  echo moved > moved.txt
fi
exit "${{MAKE_RC:-0}}"
""",
    )
    _write(bindir / "gitleaks", f'#!/bin/bash\necho "gitleaks $*" >> "{seq}"\nexit "${{GITLEAKS_RC:-0}}"\n')
    head = subprocess.check_output([GIT, "rev-parse", "HEAD"], cwd=repo, env=env, text=True).strip()
    return repo, seq, head


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PRE_COMMIT_", "L9_PUBLISH_", "GIT_", "PR_SMOKE_", "COV_CORE_", "COVERAGE_"))
    }
    env.update(
        PATH=f"{tmp_path / 'bin'}{os.pathsep}{env.get('PATH', '')}",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    return env


def _push_env(head: str, **extra: str) -> dict[str, str]:
    """The variables pre-commit 4.7.0 exports for an ordinary update push."""
    env = {
        "PRE_COMMIT_FROM_REF": "0" * 39 + "1",
        "PRE_COMMIT_TO_REF": head,
        "PRE_COMMIT_REMOTE_NAME": "origin",
        "PRE_COMMIT_REMOTE_URL": "https://github.com/cryptoxdog/IB-Odoo_19.git",
        "PRE_COMMIT_REMOTE_BRANCH": "refs/heads/fix/example",
        "PRE_COMMIT_LOCAL_BRANCH": head,
    }
    env.update(extra)
    return env


def _bound(head: str, **extra: str) -> dict[str, str]:
    binding = {"L9_PUBLISH_VALIDATED_SHA": head, "L9_PUBLISH_TARGET": "fix/example"}
    binding.update(extra)
    return _push_env(head, **binding)


def _run(repo: Path, mode: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assert BASH
    full = _base_env(repo.parent)
    full.update(env)
    return subprocess.run(
        [BASH, str(SCRIPT), mode], cwd=repo, env=full, capture_output=True, text=True, check=False, timeout=30
    )


def _run_from_publisher(repo: Path, mode: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the gate as a descendant of a process named scripts/git_push_with_pr.sh.

    The stand-in publisher lives outside the repository, so the tree stays clean.
    It does not exec: the gate must see it as a live ancestor, as it does under make pr.
    """
    assert BASH
    publisher = repo.parent / "publisher" / "scripts" / "git_push_with_pr.sh"
    publisher.parent.mkdir(parents=True, exist_ok=True)
    _write(publisher, f'#!/bin/bash\n"{BASH}" "{SCRIPT}" "$1"\nexit $?\n')
    full = _base_env(repo.parent)
    full.update(env)
    return subprocess.run(
        [BASH, str(publisher), mode], cwd=repo, env=full, capture_output=True, text=True, check=False, timeout=30
    )


def _seq(seq: Path) -> str:
    return seq.read_text(encoding="utf-8") if seq.exists() else ""


@pytest.mark.parametrize("mode", ["gitleaks", "gate"])
def test_direct_push_runs_the_full_gate(work: tuple[Path, Path, str], mode: str) -> None:
    repo, seq, head = work
    proc = _run(repo, mode, _push_env(head))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    expected = (
        "gitleaks detect --config .gitleaks.toml --redact --exit-code 2" if mode == "gitleaks" else "make pr-check"
    )
    assert _seq(seq).splitlines() == [expected]


@pytest.mark.parametrize("mode", ["gitleaks", "gate"])
def test_exact_publisher_binding_skips_the_duplicate_work(work: tuple[Path, Path, str], mode: str) -> None:
    repo, seq, head = work
    proc = _run_from_publisher(repo, mode, _bound(head))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "validated by make pr in this process" in proc.stdout
    assert _seq(seq) == ""


@pytest.mark.parametrize("mode", ["gitleaks", "gate"])
def test_forged_binding_on_a_direct_push_runs_the_full_gate(work: tuple[Path, Path, str], mode: str) -> None:
    """Setting both binding variables on a plain `git push` must not skip anything.

    Only a push made by scripts/git_push_with_pr.sh, which has just run the gate
    itself, is honoured; the variables alone are not evidence.
    """
    repo, seq, head = work
    proc = _run(repo, mode, _bound(head))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "validated by make pr" not in proc.stdout
    assert _seq(seq) != "", "a forged binding skipped validation"


@pytest.mark.parametrize("mode", ["gitleaks", "gate"])
def test_an_ancestor_that_only_names_the_publisher_does_not_count(work: tuple[Path, Path, str], mode: str) -> None:
    """A shell whose arguments merely mention scripts/git_push_with_pr.sh is not the publisher.

    Found 2026-11-04: a substring match accepted the agent's own `bash -c "... grep
    scripts/git_push_with_pr.sh ..."` shell. Only argv[0] or argv[1] may name it.
    """
    assert BASH
    repo, seq, head = work
    full = _base_env(repo.parent)
    full.update(_bound(head))
    # `; exit $?` keeps bash alive as the gate's parent instead of exec-ing it.
    command = f'"{BASH}" "{SCRIPT}" {mode}; exit $?'
    proc = subprocess.run(
        [BASH, "-c", command, "scripts/git_push_with_pr.sh"],
        cwd=repo,
        env=full,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "validated by make pr" not in proc.stdout
    assert _seq(seq) != "", "an ancestor naming the publisher in an argument skipped validation"


@pytest.mark.parametrize(
    "field,value",
    [
        ("L9_PUBLISH_VALIDATED_SHA", "f" * 40),
        ("L9_PUBLISH_TARGET", ""),
        ("L9_PUBLISH_TARGET", "fix/other"),
        ("PRE_COMMIT_REMOTE_NAME", "upstream"),
        ("PRE_COMMIT_REMOTE_BRANCH", "refs/heads/fix/other"),
    ],
)
@pytest.mark.parametrize("mode", ["gitleaks", "gate"])
def test_any_binding_mismatch_runs_the_full_gate(
    work: tuple[Path, Path, str], mode: str, field: str, value: str
) -> None:
    repo, seq, head = work
    proc = _run_from_publisher(repo, mode, _bound(head, **{field: value}))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "validated by make pr" not in proc.stdout
    assert _seq(seq) != "", f"a {field} mismatch skipped validation"


def test_failing_pr_check_refuses(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    proc = _run(repo, "gate", _push_env(head, MAKE_RC="2"))
    assert proc.returncode == 1
    assert "make pr-check failed" in proc.stderr


@pytest.mark.parametrize("rc", ["1", "2"])
def test_gitleaks_failure_or_finding_refuses(work: tuple[Path, Path, str], rc: str) -> None:
    repo, seq, head = work
    proc = _run(repo, "gitleaks", _push_env(head, GITLEAKS_RC=rc))
    assert proc.returncode == 1
    assert "gitleaks detect failed" in proc.stderr


def test_missing_gitleaks_refuses(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    (repo.parent / "bin" / "gitleaks").unlink()
    env = _push_env(head, PATH=f"{repo.parent / 'bin'}{os.pathsep}/usr/bin{os.pathsep}/bin")
    assert BASH
    if shutil.which("gitleaks", path=env["PATH"]):
        env["PATH"] = str(repo.parent / "bin")
        bindir = repo.parent / "bin"
        for tool in ("git", "bash", "env"):
            found = shutil.which(tool)
            assert found
            (bindir / tool).symlink_to(found)
    proc = _run(repo, "gitleaks", env)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "gitleaks is not on PATH" in proc.stderr


@pytest.mark.parametrize("mode", ["gitleaks", "gate"])
def test_root_history_push_is_refused(work: tuple[Path, Path, str], mode: str) -> None:
    repo, seq, head = work
    env = _push_env(head)
    del env["PRE_COMMIT_TO_REF"]
    del env["PRE_COMMIT_FROM_REF"]
    proc = _run(repo, mode, env)
    assert proc.returncode == 1
    assert "root of history is not supported" in proc.stderr
    assert _seq(seq) == ""


def test_outside_a_pre_push_is_refused(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    proc = _run(repo, "gate", {})
    assert proc.returncode == 1
    assert "runs only as a pre-push hook" in proc.stderr
    assert _seq(seq) == ""


def test_pushing_a_commit_other_than_head_is_refused(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    proc = _run(repo, "gate", _push_env("e" * 40))
    assert proc.returncode == 1
    assert "is not the checked-out HEAD" in proc.stderr
    assert _seq(seq) == ""


def test_a_forged_binding_for_another_head_is_refused_not_honoured(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    proc = _run(repo, "gate", _bound("e" * 40))
    assert proc.returncode == 1
    assert "is not the checked-out HEAD" in proc.stderr
    assert _seq(seq) == ""


@pytest.mark.parametrize("mode", ["gitleaks", "gate"])
def test_dirty_tree_is_refused_even_with_a_binding(work: tuple[Path, Path, str], mode: str) -> None:
    repo, seq, head = work
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    proc = _run(repo, mode, _bound(head))
    assert proc.returncode == 1
    assert "not clean" in proc.stderr
    assert _seq(seq) == ""


def test_worktree_change_during_validation_is_refused(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    proc = _run(repo, "gate", _push_env(head, MAKE_MOVES_HEAD="1"))
    assert proc.returncode == 1
    assert "changed during validation" in proc.stderr


def test_smoke_bypass_is_not_a_direct_push_switch(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    proc = _run(repo, "gate", _push_env(head, PR_SMOKE_BYPASS="docs only"))
    assert proc.returncode == 1
    assert "applies only to make pr-nosmoke" in proc.stderr
    assert _seq(seq) == ""


def test_unknown_mode_is_refused(work: tuple[Path, Path, str]) -> None:
    repo, seq, head = work
    proc = _run(repo, "all", _push_env(head))
    assert proc.returncode == 1
    assert "usage" in proc.stderr


def test_pr_check_runs_without_the_hooks_repo_local_git_variables(work: tuple[Path, Path, str], tmp_path: Path) -> None:
    """Git runs hooks with GIT_DIR set (absolute in a linked worktree).

    make pr-check runs test fixtures that call `git -C <their own temp repo>`.
    Inherited, GIT_DIR points those calls at this repository: on 2026-11-03 a
    direct push from a linked worktree let fixtures commit onto the branch and
    set core.bare. The gate must clear git's repo-local variables first.
    """
    repo, seq, head = work
    assert GIT
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run([GIT, "init", "-q", str(other)], env=_base_env(tmp_path), check=True)
    probe = tmp_path / "probe.log"
    _write(
        repo.parent / "bin" / "make",
        f"""#!/bin/bash
env | grep -E '^(GIT_DIR|GIT_WORK_TREE|GIT_INDEX_FILE|GIT_COMMON_DIR|GIT_PREFIX)=' >> "{probe}" || true
echo "toplevel=$(git -C "{other}" rev-parse --show-toplevel)" >> "{probe}"
exit 0
""",
    )
    git_dir = subprocess.check_output([GIT, "rev-parse", "--absolute-git-dir"], cwd=repo, text=True).strip()
    proc = _run(repo, "gate", _push_env(head, GIT_DIR=git_dir, GIT_WORK_TREE=str(repo)))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = probe.read_text(encoding="utf-8").splitlines()
    assert lines == [f"toplevel={other.resolve()}"], lines

"""make pr's audit wave must run the pinned ruff, never a newer PATH ruff.

A linked worktree has no .venv. The old Makefile fallback then executed
whatever `ruff` was on PATH. ruff 0.16.1 dies on pyproject required-version
==0.16.0, so `make lint` / `make format` failed before they linted.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "with_pinned_ruff.sh"
MAKEFILE = ROOT / "Makefile"
PIN = "0.16.0"


def _target_body(makefile: str, target: str) -> str:
    match = re.search(rf"^{re.escape(target)}:.*?(?=^\S|\Z)", makefile, flags=re.M | re.S)
    assert match, f"Makefile has no {target} target"
    return match.group(0)


def _install_script(repo: Path) -> Path:
    scripts = repo / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    dest = scripts / "with_pinned_ruff.sh"
    shutil.copy(SCRIPT, dest)
    dest.chmod(0o755)
    (repo / "requirements-dev.txt").write_text(f"ruff=={PIN}\n", encoding="utf-8")
    return dest


def _fake_ruff(path: Path, version: str, marker: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # marker is quoted so a worktree path that contains spaces still records.
    quoted = str(marker).replace("'", "'\\''")
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  echo ruff {version}\n"
        "  exit 0\n"
        "fi\n"
        f"echo \"$1\" >> '{quoted}'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run(repo: Path, script: Path, path: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = path
    env.pop("RUFF", None)
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_make_lint_and_format_call_the_pinned_wrapper() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "|| echo ruff" not in text
    assert "$(RUFF)" not in text
    for target in ("lint", "format", "format-fix"):
        body = _target_body(text, target)
        assert "bash scripts/with_pinned_ruff.sh" in body
        assert "\truff " not in body


def test_checkout_venv_wins_over_a_newer_path_ruff(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    script = _install_script(repo)
    marker = tmp_path / "ran"
    _fake_ruff(repo / ".venv" / "bin" / "ruff", PIN, marker)
    newer = tmp_path / "bin" / "ruff"
    _fake_ruff(newer, "0.16.1", marker)
    proc = _run(repo, script, f"{newer.parent}{os.pathsep}{os.environ['PATH']}", "check", ".")
    assert proc.returncode == 0, proc.stderr
    assert marker.read_text(encoding="utf-8").splitlines() == ["check"]


def test_path_ruff_is_used_only_when_it_matches_the_pin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    script = _install_script(repo)
    marker = tmp_path / "ran"
    pinned = tmp_path / "bin" / "ruff"
    _fake_ruff(pinned, PIN, marker)
    proc = _run(repo, script, f"{pinned.parent}{os.pathsep}/usr/bin{os.pathsep}/bin", "format", "--check", ".")
    assert proc.returncode == 0, proc.stderr
    assert marker.read_text(encoding="utf-8").splitlines() == ["format"]


def test_worktree_without_venv_uses_the_primary_checkout_venv(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=main, env=env, check=True, capture_output=True)
    (main / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=main, env=env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=main, env=env, check=True, capture_output=True)
    worktree = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", str(worktree)], cwd=main, env=env, check=True, capture_output=True)

    script = _install_script(worktree)
    marker = tmp_path / "ran"
    _fake_ruff(main / ".venv" / "bin" / "ruff", PIN, marker)
    newer = tmp_path / "bin" / "ruff"
    _fake_ruff(newer, "0.16.1", marker)
    uv_marker = tmp_path / "uv"
    uv = tmp_path / "bin" / "uv"
    uv.write_text(f"#!/bin/sh\necho uv >> '{uv_marker}'\nexit 0\n", encoding="utf-8")
    uv.chmod(0o755)

    proc = _run(
        worktree,
        script,
        f"{newer.parent}{os.pathsep}/usr/bin{os.pathsep}/bin{os.pathsep}/opt/homebrew/bin",
        "check",
        ".",
    )
    assert proc.returncode == 0, proc.stderr
    assert marker.read_text(encoding="utf-8").splitlines() == ["check"]
    assert not uv_marker.exists()


def test_newer_path_ruff_is_not_executed_when_uv_can_fetch_the_pin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    script = _install_script(repo)
    wrong = tmp_path / "wrong"
    _fake_ruff(tmp_path / "bin" / "ruff", "0.16.1", wrong)
    uv_log = tmp_path / "uv"
    quoted = str(uv_log).replace("'", "'\\''")
    uv = tmp_path / "bin" / "uv"
    uv.write_text(
        f"#!/bin/sh\necho \"$*\" >> '{quoted}'\nexit 0\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    proc = _run(repo, script, f"{uv.parent}{os.pathsep}/usr/bin{os.pathsep}/bin", "check", ".")
    assert proc.returncode == 0, proc.stderr
    assert not wrong.exists()
    assert uv_log.read_text(encoding="utf-8").strip() == f"tool run --from ruff=={PIN} ruff check ."


def test_divergent_pyproject_pin_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    script = _install_script(repo)
    (repo / "pyproject.toml").write_text('required-version = "==0.16.1"\n', encoding="utf-8")
    proc = _run(repo, script, "/usr/bin:/bin", "--version")
    assert proc.returncode != 0
    assert f"ruff=={PIN}" in proc.stderr
    assert "==0.16.1" in proc.stderr

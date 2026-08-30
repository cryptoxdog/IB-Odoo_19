"""Negative-test contract for the BAN001 guard (ci/check_banned_identifier.py).

Pure Python: no Odoo import, so this runs in the `pure-python-tests` CI job.

Every violating fixture is constructed at runtime from ASCII code points inside a
disposable temporary git repository. The prohibited sequence is therefore never
committed to this repository, and this test file is itself BAN001-clean — which
the guard verifies when it scans the tracked tree.
"""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(REPO_ROOT, "ci", "check_banned_identifier.py")

# Reconstructed at runtime — never spelled contiguously in repository bytes.
BANNED = bytes([99, 105, 101, 116, 114, 97, 100, 101]).decode("ascii")


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    """A disposable git repo containing one clean tracked file."""
    r = tmp_path / "sandbox"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "test@example.invalid")
    _git(r, "config", "user.name", "test")
    (r / "clean.txt").write_text("no prohibited identifier here\n")
    _git(r, "add", "clean.txt")
    return r


def run_guard(repo):
    return subprocess.run([sys.executable, GUARD], cwd=repo, capture_output=True, text=True)


def test_guard_is_itself_clean():
    """The guard must not contain the sequence it bans."""
    assert BANNED not in open(GUARD, encoding="utf-8").read().lower()


def test_clean_repository_passes(repo):
    assert run_guard(repo).returncode == 0


def test_real_repository_passes():
    """The actual repository must satisfy the invariant."""
    result = run_guard(REPO_ROOT)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "casing",
    [BANNED, BANNED.upper(), BANNED.capitalize(), BANNED[:3] + BANNED[3:].upper()],
    ids=["lowercase", "uppercase", "capitalized", "mixed"],
)
def test_content_violation_fails(repo, casing):
    (repo / "doc.md").write_text(f"legacy {casing} reference\n")
    _git(repo, "add", "doc.md")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "doc.md" in result.stderr


def test_filename_violation_fails(repo):
    """A prohibited file name fails even when the contents are clean."""
    (repo / f"{BANNED}_notes.md").write_text("contents are clean\n")
    _git(repo, "add", f"{BANNED}_notes.md")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "file name" in result.stderr


def test_directory_violation_fails(repo):
    """A prohibited directory component fails even when leaf and contents are clean."""
    d = repo / f"{BANNED}_export"
    d.mkdir()
    (d / "payload.md").write_text("contents are clean\n")
    _git(repo, "add", f"{BANNED}_export/payload.md")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "directory name" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics required")
def test_symlink_target_violation_fails(repo):
    """A clean link name pointing at a prohibited target fails."""
    os.symlink(f"../{BANNED}_source/data.csv", repo / "link.csv")
    _git(repo, "add", "link.csv")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "symlink target" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink semantics required")
def test_unmaterialised_symlink_target_violation_fails(repo):
    """A tracked symlink absent from the worktree is still inspected via the index.

    Regression guard: reading the target with os.readlink() alone would skip the
    entry entirely and report the repository clean.
    """
    os.symlink(f"../{BANNED}_source/data.csv", repo / "ghost.csv")
    _git(repo, "add", "ghost.csv")
    os.remove(repo / "ghost.csv")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "symlink target" in result.stderr


def test_binary_violation_fails(repo):
    """Binary files are scanned as raw bytes, not skipped as non-text."""
    payload = b"\x00\x01\x02PNG\x00" + BANNED.encode("ascii") + b"\x00\xff\xfe"
    (repo / "blob.bin").write_bytes(payload)
    _git(repo, "add", "blob.bin")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "blob.bin" in result.stderr


def test_match_spanning_read_boundary_fails(repo):
    """A match straddling the streaming chunk seam must still be detected."""
    chunk = 1 << 20
    padding = b"x" * (chunk - 4)
    (repo / "big.bin").write_bytes(padding + BANNED.encode("ascii") + b"y" * 32)
    _git(repo, "add", "big.bin")
    assert run_guard(repo).returncode == 1


@pytest.mark.parametrize("near", ["cie_trade", "citrade", "cie-trade", "cietrde", "trade"], ids=lambda s: s)
def test_near_matches_pass(repo, near):
    """Only the exact sequence is prohibited; lookalikes must not fail the build."""
    (repo / "near.md").write_text(f"{near} is not the prohibited identifier\n")
    _git(repo, "add", "near.md")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


def test_deleted_worktree_file_still_evaluated_from_index(repo):
    """Content is judged from the index, so deleting the file cannot hide it.

    The index is what a commit will contain. Reading the worktree instead would
    let a staged violation escape simply because the file was removed on disk,
    and would also false-block on any unrelated deletion in a dirty tree.
    """
    (repo / "staged.md").write_text(f"legacy {BANNED} reference\n")
    _git(repo, "add", "staged.md")
    os.remove(repo / "staged.md")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "staged.md" in result.stderr


def test_clean_file_deleted_from_worktree_does_not_false_block(repo):
    """A deleted but clean tracked file is not a violation and not an error."""
    (repo / "gone.md").write_text("nothing prohibited here\n")
    _git(repo, "add", "gone.md")
    os.remove(repo / "gone.md")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


def test_outside_git_repository_fails_closed(tmp_path):
    """No index means no verdict: exit 2, never a silent pass."""
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    result = run_guard(outside)
    assert result.returncode == 2
    assert "FAIL-CLOSED" in result.stderr

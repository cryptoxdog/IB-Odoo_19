"""Regression guard: blocking Make targets must propagate their checker's exit status.

`make deps-check` and `make cron-check` once wrapped their checkers in `|| true`,
so a real circular dependency or cron-invariant violation still exited 0 (false
green). These tests run the repository's real Makefile recipes against stub
checkers in a scratch directory: a failing checker must fail the target, and a
passing checker must pass it. Re-adding `|| true` (or any wrapper that swallows
the status) fails the first case.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
STUB_MARKER = "STUB-CHECKER-RAN"

# Make target -> checker path its recipe invokes (relative to the working dir).
BLOCKING_TARGETS = {
    "deps-check": "ci/check_circular_deps.py",
    "cron-check": "tools/cron_invariant_check.py",
}


def _run_target_with_stub(tmp_path: Path, target: str, checker: str, exit_code: int) -> subprocess.CompletedProcess:
    make = shutil.which("make")
    assert make is not None, "GNU make is required to exercise the Makefile recipes"
    stub = tmp_path / checker
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(f"import sys\nprint({STUB_MARKER!r})\nsys.exit({exit_code})\n", encoding="utf-8")
    # The stubs are not code under test. Without this, pytest-cov's subprocess
    # hook (COV_CORE_*) starts coverage inside them from tmp_path, where
    # pyproject's branch=true is not found, and the statement-only data it
    # writes into the parent run's data file breaks `--cov` combine.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE_", "COVERAGE_"))}
    return subprocess.run(
        [make, "--no-print-directory", "-C", str(tmp_path), "-f", str(MAKEFILE), target],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env=env,
    )


@pytest.mark.parametrize(("target", "checker"), sorted(BLOCKING_TARGETS.items()))
def test_failing_checker_fails_the_make_target(tmp_path, target, checker):
    proc = _run_target_with_stub(tmp_path, target, checker, exit_code=1)
    output = proc.stdout + proc.stderr
    assert STUB_MARKER in output, f"make {target} did not invoke {checker}:\n{output}"
    assert proc.returncode != 0, f"make {target} swallowed a failing {checker} (false green):\n{output}"


@pytest.mark.parametrize(("target", "checker"), sorted(BLOCKING_TARGETS.items()))
def test_passing_checker_passes_the_make_target(tmp_path, target, checker):
    proc = _run_target_with_stub(tmp_path, target, checker, exit_code=0)
    output = proc.stdout + proc.stderr
    assert STUB_MARKER in output, f"make {target} did not invoke {checker}:\n{output}"
    assert proc.returncode == 0, f"make {target} failed although {checker} passed:\n{output}"

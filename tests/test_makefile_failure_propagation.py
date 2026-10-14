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
import sys
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


# ---------------------------------------------------------------------------
# `make runtime-gates` — the launch-gate aggregator (tests/runtime_gates/README.md)
# ---------------------------------------------------------------------------
# A gate exits 0 (PASS), 77 (SKIPPED: a documented precondition is unmet, so
# the gate did not run) or anything else (FAIL). The aggregator's own contract
# is that a skipped gate "is never counted as a pass: a gate that did not run
# must not read green". These tests drive the real recipe with stub gate
# scripts and pin the exit code that contract implies: 0 only when every gate
# ran and passed, 77 when nothing failed but something did not run, non-zero
# (not 77) when any gate failed. Before this pin, a run in which every
# mandatory gate was skipped exited 0 — a green acceptance result that proved
# nothing (FX-005).
GATE_SKIP_EXIT = 77


def _write_runtime_gate_stubs(tmp_path: Path, gate_exit_codes: dict[str, int]) -> dict[str, str]:
    """Lay out the recipe's prerequisites and the stub gate scripts under ``tmp_path``.

    `runtime-gates` depends on `check-local-runtime` (runs
    `scripts/setup_local_runtime.sh --check`) and `gate-db` (`psql -lqt` to see
    whether the gate database exists). Both are stubbed so the test exercises
    only the aggregation logic, never a PostgreSQL server or an Odoo venv.
    Returns the environment overrides the recipe needs.
    """
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "setup_local_runtime.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    # `gate-db` greps `psql -lqt` for the gate database; list it so createdb is never reached.
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    psql = stub_bin / "psql"
    psql.write_text("#!/bin/sh\necho ' c1c6_test | odoo | UTF8'\n", encoding="utf-8")
    psql.chmod(0o755)
    createdb = stub_bin / "createdb"
    createdb.write_text("#!/bin/sh\necho 'createdb must not run' >&2\nexit 9\n", encoding="utf-8")
    createdb.chmod(0o755)
    # The recipe runs each gate with "$(L9_ODOO_VENV)/bin/python".
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(sys.executable)
    gates = tmp_path / "tests" / "runtime_gates"
    gates.mkdir(parents=True)
    for name, code in gate_exit_codes.items():
        (gates / f"run_{name}.py").write_text(
            f"import sys\nprint({STUB_MARKER!r}, {name!r})\nsys.exit({code})\n", encoding="utf-8"
        )
    return {
        "PATH": f"{stub_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "L9_ODOO_VENV": str(tmp_path / "venv"),
    }


def _run_runtime_gates(tmp_path: Path, gate_exit_codes: dict[str, int]) -> subprocess.CompletedProcess:
    make = shutil.which("make")
    assert make is not None, "GNU make is required to exercise the Makefile recipes"
    overrides = _write_runtime_gate_stubs(tmp_path, gate_exit_codes)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE_", "COVERAGE_"))}
    env.update(overrides)
    return subprocess.run(
        [make, "--no-print-directory", "-C", str(tmp_path), "-f", str(MAKEFILE), "runtime-gates"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env=env,
    )


def _assert_every_gate_ran(proc: subprocess.CompletedProcess, gate_exit_codes: dict[str, int]) -> str:
    output = proc.stdout + proc.stderr
    for name in gate_exit_codes:
        assert f"{STUB_MARKER} {name}" in output, f"make runtime-gates did not invoke run_{name}.py:\n{output}"
    return output


def test_runtime_gates_does_not_count_f1_as_passed(tmp_path):
    """F1 is outside this aggregate. A green stub of that filename is not a pass."""
    gates = {"a": 0, "b": 0, "f1_f3_full_import": 0}
    proc = _run_runtime_gates(tmp_path, gates)
    output = proc.stdout + proc.stderr
    assert f"{STUB_MARKER} a" in output and f"{STUB_MARKER} b" in output, output
    assert f"{STUB_MARKER} f1_f3_full_import" not in output, output
    assert "NOT IN THIS AGGREGATE" in output and "not a pass" in output, output
    assert "F1–F3: not run by this aggregate (not a pass)" in output, output
    assert "2 passed, 0 skipped, 0 failed" in output, output
    assert proc.returncode == 0, output


def test_runtime_gate_refuses_f1_on_the_no_docker_target(tmp_path):
    make = shutil.which("make")
    assert make is not None
    overrides = _write_runtime_gate_stubs(tmp_path, {"f1_f3_full_import": 0})
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE_", "COVERAGE_"))}
    env.update(overrides)
    proc = subprocess.run(
        [
            make,
            "--no-print-directory",
            "-C",
            str(tmp_path),
            "-f",
            str(MAKEFILE),
            "runtime-gate",
            "g=run_f1_f3_full_import.py",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env=env,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, output
    assert "not a pass" in output, output
    assert STUB_MARKER not in output, output


def test_runtime_gates_pass_only_when_every_gate_passed(tmp_path):
    gates = {"a": 0, "b": 0, "c": 0}
    proc = _run_runtime_gates(tmp_path, gates)
    output = _assert_every_gate_ran(proc, gates)
    assert "3 passed, 0 skipped, 0 failed" in output, output
    assert proc.returncode == 0, f"make runtime-gates failed although every gate passed:\n{output}"


@pytest.mark.parametrize(
    "gates",
    [
        pytest.param({"a": GATE_SKIP_EXIT, "b": GATE_SKIP_EXIT}, id="every-gate-skipped"),
        pytest.param({"a": 0, "b": GATE_SKIP_EXIT, "c": 0}, id="one-gate-skipped"),
    ],
)
def test_runtime_gates_skipped_gate_never_reads_green(tmp_path, gates):
    """A gate that did not run cannot contribute a passing acceptance result.

    The recipe already reports the skip; the exit code must agree with it. 77
    is the repository's existing "did not run, never a pass" code, and it is
    distinct from a real failure so a caller can tell INCOMPLETE from FAILED.
    """
    proc = _run_runtime_gates(tmp_path, gates)
    output = _assert_every_gate_ran(proc, gates)
    skipped = sum(1 for code in gates.values() if code == GATE_SKIP_EXIT)
    assert f"{skipped} skipped, 0 failed" in output, output
    assert proc.returncode != 0, (
        f"make runtime-gates read green with {skipped} gate(s) skipped (false green):\n{output}"
    )
    # GNU make folds every recipe failure into its own exit 2, so the verdict
    # that tells INCOMPLETE from FAILED is the recipe's printed line and the
    # recipe's own exit status (77), which make reports verbatim.
    assert "INCOMPLETE" in output and f"Error {GATE_SKIP_EXIT}" in output, (
        f"an incomplete run must be reported as INCOMPLETE (recipe exit {GATE_SKIP_EXIT}), not as a defect:\n{output}"
    )
    assert "  failed:" not in output, output


@pytest.mark.parametrize(
    "gates",
    [
        pytest.param({"a": 0, "b": 1, "c": 0}, id="one-gate-failed"),
        pytest.param({"a": GATE_SKIP_EXIT, "b": 1}, id="failed-outranks-skipped"),
        pytest.param({"a": 0, "b": 2}, id="crash-is-a-failure"),
    ],
)
def test_runtime_gates_any_failed_gate_fails_the_target(tmp_path, gates):
    proc = _run_runtime_gates(tmp_path, gates)
    output = _assert_every_gate_ran(proc, gates)
    assert "1 failed" in output and "  failed: run_b.py" in output, output
    assert proc.returncode != 0, f"make runtime-gates swallowed a failing gate (false green):\n{output}"
    assert "INCOMPLETE" not in output and f"Error {GATE_SKIP_EXIT}" not in output, (
        f"a failed gate is a defect, never reported as merely INCOMPLETE:\n{output}"
    )

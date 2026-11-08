"""F1 stub commits may land only on a clone this worktree owns, and must leave with it.

``scripts/test_env.sh`` is the lifecycle. These witnesses never create or delete a
real database: a refused name does not reach the script, a foreign owner is
refused by the real ``assert-clone`` against a docker stub, and retirement is
the script's ``drop`` (its filestore-aware database manager), not SQL from the gate.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tests" / "runtime_gates" / "run_f1_f3_full_import.py"
ENV = ROOT / "tests" / "runtime_gates" / "_runtime_env.py"
SHELL = ROOT / "scripts" / "test_env.sh"
sys.path.insert(0, str(ROOT / "tests" / "runtime_gates"))

from _runtime_env import execute_owned_f1, prove_owned_f1_clone  # noqa: E402

from tests.test_test_env_safety import _clone, _fingerprint, _stateful, _template  # noqa: E402

OWNED = "odoo_test_f1_gate"


def _recording_runner(responses: dict[str, int]):
    calls: list[list[str]] = []

    def runner(args: list[str]) -> int:
        calls.append(list(args))
        return responses[args[0]]

    return calls, runner


def test_f1_gate_deletes_only_through_the_test_env_lifecycle():
    """The gate has no DROP DATABASE. Retirement is test_env.sh drop, which removes the filestore."""
    source = GATE.read_text()
    assert "DROP DATABASE" not in source
    assert "atexit" not in source
    assert "execute_owned_f1(_REQUESTED_DB, _run)" in source
    env = ENV.read_text()
    retire = env.split("def retire_owned_f1_clone", 1)[1].split("\ndef ", 1)[0]
    assert 'invoke_test_env("drop", name, runner=runner)' in retire
    shell = SHELL.read_text()
    assert "drop an owned clone (database and filestore)" in shell
    drop = shell.split("drop_owned_clone() {", 1)[1].split("\n}\n", 1)[0]
    assert 'odoo_db "drop-$target" drop "$target"' in drop
    assert "DROP DATABASE" not in drop
    tree = ast.parse(source)
    run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run")
    assert any(isinstance(node, ast.FunctionDef) and node.name == "make_connection" for node in run.body)


def test_foreign_owned_clone_is_refused_without_modification_or_deletion(tmp_path):
    fp = _fingerprint(tmp_path)
    (tmp_path / "stub.log").unlink(missing_ok=True)
    tpl, marker = _template(fp)
    databases = {tpl: marker, OWNED: _clone(fp, owner="agentb")}
    calls: list[list[str]] = []
    started: list[str] = []

    def runner(args: list[str]) -> int:
        calls.append(list(args))
        result = _stateful(tmp_path, databases, *args)
        runner.stderr = result.stderr
        return result.returncode

    def body(name: str) -> int:
        started.append(name)
        return 0

    with pytest.raises(SystemExit) as caught:
        execute_owned_f1(OWNED, body, runner=runner)
    assert caught.value.code == 2
    assert "owned by 'agentb'" in runner.stderr
    assert started == []
    assert calls == [["assert-clone", OWNED]]
    log = (tmp_path / "stub.log").read_text()
    for marker_text in ("DROP DATABASE", " CREATE DATABASE", " drop ", "entrypoint rm"):
        assert marker_text not in log, marker_text
    assert json.loads((tmp_path / "state.json").read_text()) == databases


def test_valid_owned_clone_is_accepted(tmp_path):
    fp = _fingerprint(tmp_path)
    (tmp_path / "stub.log").unlink(missing_ok=True)
    tpl, marker = _template(fp)
    databases = {tpl: marker, OWNED: _clone(fp)}
    calls: list[list[str]] = []

    def runner(args: list[str]) -> int:
        calls.append(list(args))
        result = _stateful(tmp_path, databases, *args)
        runner.stdout = result.stdout
        return result.returncode

    assert prove_owned_f1_clone(OWNED, runner=runner) == OWNED
    assert calls == [["assert-clone", OWNED]]
    assert f"clone of {tpl}" in runner.stdout
    log = (tmp_path / "stub.log").read_text()
    assert " drop " not in log
    assert "DROP DATABASE" not in log


@pytest.mark.parametrize(
    "name",
    ["odoo_test_crm1r1", "odoo_test_crm1live", "c1c6_test", "odoo", "odoo_test_f1_staging", "odoo_test_f1_prod"],
)
def test_integration_or_production_target_is_refused_before_the_lifecycle(name):
    def runner(args: list[str]) -> int:
        raise AssertionError(args)

    def body(db: str) -> int:
        raise AssertionError(db)

    with pytest.raises(SystemExit) as caught:
        execute_owned_f1(name, body, runner=runner)
    assert "refusing stub CRM gate" in str(caught.value)


def test_successful_gate_retires_the_owned_clone():
    calls, runner = _recording_runner({"assert-clone": 0, "drop": 0})
    assert execute_owned_f1(OWNED, lambda name: 0, runner=runner) == 0
    assert calls == [["assert-clone", OWNED], ["drop", OWNED]]


def test_failed_gate_retires_the_owned_clone():
    calls, runner = _recording_runner({"assert-clone": 0, "drop": 0})

    def body(name: str) -> int:
        return 1

    with pytest.raises(SystemExit) as caught:
        execute_owned_f1(OWNED, body, runner=runner)
    assert caught.value.code == 1
    assert calls == [["assert-clone", OWNED], ["drop", OWNED]]


def test_crashed_gate_still_retires_the_owned_clone():
    calls, runner = _recording_runner({"assert-clone": 0, "drop": 0})

    def body(name: str) -> int:
        raise RuntimeError("gate failed")

    with pytest.raises(RuntimeError, match="gate failed"):
        execute_owned_f1(OWNED, body, runner=runner)
    assert calls == [["assert-clone", OWNED], ["drop", OWNED]]


def test_retirement_failure_is_not_a_successful_gate():
    calls, runner = _recording_runner({"assert-clone": 0, "drop": 3})
    with pytest.raises(SystemExit) as caught:
        execute_owned_f1(OWNED, lambda name: 0, runner=runner)
    assert caught.value.code == 3
    assert calls == [["assert-clone", OWNED], ["drop", OWNED]]

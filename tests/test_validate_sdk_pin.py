"""ADR-011 (amended 2026-11-08): Gate_SDK is declared on the moving major channel ``v1``.

Runs ``scripts/validate_sdk_pin.py`` against the real tree and against fixture
trees for each refusal: a commit sha, a branch, a fork, a second declaration,
and a sha hidden in a file other than requirements.txt. Pure Python; no Odoo.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_sdk_pin.py"

_spec = importlib.util.spec_from_file_location("validate_sdk_pin", SCRIPT)
assert _spec is not None and _spec.loader is not None
validate_sdk_pin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_sdk_pin)

CHANNEL_LINE = "constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@v1\n"


def _tree(tmp_path: Path, requirements: str, extra: dict[str, str] | None = None) -> Path:
    (tmp_path / "requirements.txt").write_text("requests>=2\n" + requirements, encoding="utf-8")
    for rel, text in (extra or {}).items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


def test_repository_declares_the_v1_channel() -> None:
    assert validate_sdk_pin.check_tree(ROOT) == []


def test_script_passes_on_the_repository() -> None:
    completed = subprocess.run([sys.executable, str(SCRIPT)], check=False, capture_output=True, text=True, cwd=ROOT)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS" in completed.stdout


def test_channel_declaration_passes(tmp_path: Path) -> None:
    assert validate_sdk_pin.check_tree(_tree(tmp_path, CHANNEL_LINE)) == []


@pytest.mark.parametrize(
    ("line", "fragment"),
    [
        pytest.param(
            "constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@7ec6cdf5e26c837057ca35b7324a88de4d499ea3\n",
            "commit sha",
            id="exact-sha",
        ),
        pytest.param(
            "constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@main\n",
            "branch",
            id="main",
        ),
        pytest.param(
            "constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@v1.3.2\n",
            "is not 'v1'",
            id="exact-release-tag",
        ),
        pytest.param(
            "constellation-node-sdk @ git+https://github.com/cryptoxdog/Gate_SDK.git@v1\n",
            "forbidden fork",
            id="fork",
        ),
        pytest.param("constellation-node-sdk>=1.3\n", "not a git requirement", id="index-range"),
    ],
)
def test_non_channel_declarations_fail(tmp_path: Path, line: str, fragment: str) -> None:
    errors = validate_sdk_pin.check_tree(_tree(tmp_path, line))
    assert any(fragment in error for error in errors), errors


def test_missing_declaration_fails(tmp_path: Path) -> None:
    errors = validate_sdk_pin.check_tree(_tree(tmp_path, ""))
    assert any("found 0" in error for error in errors), errors


def test_second_declaration_fails(tmp_path: Path) -> None:
    errors = validate_sdk_pin.check_tree(_tree(tmp_path, CHANNEL_LINE + CHANNEL_LINE))
    assert any("found 2" in error for error in errors), errors


def test_sha_in_a_workflow_fails(tmp_path: Path) -> None:
    workflow = "run: pip install 'constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@bc1c74c'\n"
    tree = _tree(tmp_path, CHANNEL_LINE, {".github/workflows/ci.yml": workflow})
    errors = validate_sdk_pin.check_tree(tree)
    assert errors == [
        ".github/workflows/ci.yml: Gate_SDK declared by commit sha bc1c74c; "
        "the consumer contract is the moving major channel v1"
    ]


def test_missing_requirements_fails(tmp_path: Path) -> None:
    assert validate_sdk_pin.check_tree(tmp_path) == ["requirements.txt: declaring surface is missing"]

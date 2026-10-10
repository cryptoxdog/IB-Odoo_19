"""GMP-NC-A: one weak-test owner, no pseudo runtime-coverage claim."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXER_PATH = ROOT / "ci" / "weak_test_fixer.py"
AUDIT_PATH = ROOT / "scripts" / "audit" / "test_audit.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fixer_module = _load("weak_test_fixer_under_test", FIXER_PATH)
audit_module = _load("test_audit_under_test", AUDIT_PATH)


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def _flagged(root: Path) -> set[tuple[str, str]]:
    fixer = fixer_module.WeakTestFixer(root)
    found = set()
    for test_file in fixer.iter_test_files():
        relative = str(test_file.relative_to(root))
        for item in fixer.analyze_test_file(test_file):
            found.add((relative, item["name"]))
    return found


def test_bare_assert_pytest_raises_and_assertion_error_are_not_flagged(tmp_path: Path):
    _write(
        tmp_path,
        "tests/test_forms.py",
        """
        import pytest

        def test_bare():
            assert True

        def test_raises():
            with pytest.raises(ValueError):
                raise ValueError("nope")

        def test_explicit():
            raise AssertionError("contract")

        def test_unittest(self):
            self.assertEqual(1, 1)

        def test_assert_helper():
            assert_contract()

        def test_underscore_helper():
            _assert_contract()
        """,
    )
    assert _flagged(tmp_path) == set()


def test_non_assertion_helpers_and_empty_tests_are_flagged(tmp_path: Path):
    _write(
        tmp_path,
        "tests/test_weak.py",
        """
        def test_check():
            check_ready()

        def test_private_check():
            _check_ready()

        def test_validate():
            validate_ready()

        def test_run():
            _run_ready()

        def test_safe():
            _safe_ready()

        def test_empty():
            return None
        """,
    )
    assert _flagged(tmp_path) == {
        ("tests/test_weak.py", "test_check"),
        ("tests/test_weak.py", "test_private_check"),
        ("tests/test_weak.py", "test_validate"),
        ("tests/test_weak.py", "test_run"),
        ("tests/test_weak.py", "test_safe"),
        ("tests/test_weak.py", "test_empty"),
    }


def test_addon_tests_are_scanned_and_script_trees_are_not(tmp_path: Path):
    _write(
        tmp_path,
        "plasticos_sample/tests/test_addon.py",
        """
        def test_addon_empty():
            return None
        """,
    )
    _write(
        tmp_path,
        "scripts/nested/tests/test_hidden.py",
        """
        def test_hidden_empty():
            return None
        """,
    )
    assert _flagged(tmp_path) == {("plasticos_sample/tests/test_addon.py", "test_addon_empty")}


def test_extended_audit_uses_the_owner_and_drops_coverage_claims(tmp_path: Path):
    _write(
        tmp_path,
        "plasticos_sample/models/thing.py",
        """
        class Thing:
            _name = "plasticos.thing"
        """,
    )
    _write(
        tmp_path,
        "plasticos_sample/tests/test_addon.py",
        """
        def test_addon_empty():
            return None
        """,
    )
    audit = audit_module.TestAudit(tmp_path)
    assert audit.get_models_without_tests() == []
    findings = audit.check_weak_tests()
    assert [(item["type"], item["file"], item["test"]) for item in findings] == [
        ("WEAK_TEST", "plasticos_sample/tests/test_addon.py", "test_addon_empty")
    ]
    assert all(item["type"] != "NO_TEST_COVERAGE" for item in findings)

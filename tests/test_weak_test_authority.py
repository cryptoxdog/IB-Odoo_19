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


_EMPTY_TEST = """
def test_empty():
    return None
"""


def _population(root: Path) -> set[str]:
    fixer = fixer_module.WeakTestFixer(root)
    return {str(path.relative_to(root)) for path in fixer.iter_test_files()}


def test_top_level_nested_suites_are_scanned(tmp_path: Path):
    for relative in (
        "tests/test_root.py",
        "tests/contracts/test_contract.py",
        "tests/integration/test_flow.py",
        "tests/integration/deep/test_deeper.py",
    ):
        _write(tmp_path, relative, _EMPTY_TEST)
    assert _population(tmp_path) == {
        "tests/test_root.py",
        "tests/contracts/test_contract.py",
        "tests/integration/test_flow.py",
        "tests/integration/deep/test_deeper.py",
    }
    assert ("tests/integration/deep/test_deeper.py", "test_empty") in _flagged(tmp_path)


def test_addon_nested_suites_are_scanned(tmp_path: Path):
    for relative in (
        "plasticos_sample/tests/test_addon.py",
        "plasticos_sample/tests/common/test_nested.py",
    ):
        _write(tmp_path, relative, _EMPTY_TEST)
    assert _population(tmp_path) == {
        "plasticos_sample/tests/test_addon.py",
        "plasticos_sample/tests/common/test_nested.py",
    }


def test_excluded_directories_and_non_test_files_stay_excluded(tmp_path: Path):
    _write(tmp_path, "tests/contracts/test_kept.py", _EMPTY_TEST)
    for relative in (
        ".venv/lib/pkg/tests/test_vendor.py",
        "venv/pkg/tests/test_vendor.py",
        "lib/site-packages/pkg/tests/test_vendor.py",
        "node_modules/pkg/tests/test_vendor.py",
        "odoo-enterprise/documents/tests/test_vendor.py",
        "odoo/addons/base/tests/test_core.py",
        "Current Work - IGNORE/tests/test_scratch.py",
        "scripts/nested/tests/test_script.py",
        "tools/tests/test_tool.py",
        "skills/sample/tests/test_skill.py",
        "tests/__pycache__/test_cached.py",
        "plasticos_sample/models/test_not_in_tests.py",
        "tests/contracts/helpers.py",
        "tests/contracts/conftest.py",
    ):
        _write(tmp_path, relative, _EMPTY_TEST)
    assert _population(tmp_path) == {"tests/contracts/test_kept.py"}


def test_checkout_location_does_not_hide_the_population(tmp_path: Path):
    root = tmp_path / "tools" / "scripts" / "checkout"
    _write(root, "tests/contracts/test_contract.py", _EMPTY_TEST)
    assert _population(root) == {"tests/contracts/test_contract.py"}


def test_nested_suites_keep_assertion_recognition(tmp_path: Path):
    _write(
        tmp_path,
        "tests/integration/test_forms.py",
        """
        import pytest

        def test_bare():
            assert True

        def test_raises():
            with pytest.raises(ValueError):
                raise ValueError("nope")

        def test_explicit():
            raise AssertionError("contract")

        def test_helper_is_not_evidence():
            check_ready()
        """,
    )
    assert _flagged(tmp_path) == {("tests/integration/test_forms.py", "test_helper_is_not_evidence")}


def test_both_consumers_receive_the_same_population(tmp_path: Path):
    for relative in (
        "tests/test_root.py",
        "tests/contracts/test_contract.py",
        "plasticos_sample/tests/test_addon.py",
        "plasticos_sample/tests/common/test_nested.py",
        "scripts/nested/tests/test_script.py",
    ):
        _write(tmp_path, relative, _EMPTY_TEST)
    audit_files = {item["file"] for item in audit_module.TestAudit(tmp_path).check_weak_tests()}
    assert audit_files == _population(tmp_path)
    assert audit_files == {
        "tests/test_root.py",
        "tests/contracts/test_contract.py",
        "plasticos_sample/tests/test_addon.py",
        "plasticos_sample/tests/common/test_nested.py",
    }


def test_repository_nested_suites_are_in_the_owner_population():
    population = _population(ROOT)
    assert any(path.startswith("tests/contracts/") for path in population)
    assert any(path.startswith("tests/integration/") for path in population)
    assert {path for path in population if path.startswith("tests/")} == {
        str(path.relative_to(ROOT)) for path in (ROOT / "tests").rglob("test_*.py") if "__pycache__" not in path.parts
    }


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


def test_local_helpers_that_assert_are_resolved_one_hop(tmp_path: Path):
    _write(
        tmp_path,
        "tests/test_helpers.py",
        """
        def _module_check(value):
            assert value == 1

        class Base:
            def _inherited_check(self):
                self.assertTrue(True)

        class TestCron(Base):
            def _run_twice(self, name):
                ok = run(name)
                if ok is None:
                    self.skipTest(name)
                self.assertTrue(ok)

            def _run_cron_safely(self, name):
                try:
                    run(name)
                except Exception as exc:
                    self.fail(str(exc))

            def test_twice(self):
                self._run_twice("cron")

            def test_safely(self):
                self._run_cron_safely("cron")

            def test_inherited(self):
                self._inherited_check()

            def test_module_function(self):
                _module_check(1)
        """,
    )
    assert _flagged(tmp_path) == set()


def test_unproven_local_helpers_stay_flagged(tmp_path: Path):
    _write(
        tmp_path,
        "tests/test_bad_helpers.py",
        """
        def _module_noop(value):
            return value

        def _module_inner():
            assert True

        def _module_two_hop():
            _module_inner()

        class TestOther:
            def _owned_elsewhere(self):
                self.assertTrue(True)

        class TestCron:
            def _asserts(self):
                self.assertTrue(True)

            def _no_assert(self):
                run("cron")

            def _assert_named_but_silent(self):
                run("cron")

            def _dead_assert(self):
                return None
                self.assertTrue(True)

            def _false_branch(self):
                if False:
                    self.assertTrue(True)

            def test_uncalled(self):
                run("cron")

            def test_called_after_return(self):
                return None
                self._asserts()

            def test_non_asserting(self):
                self._no_assert()

            def test_name_is_not_evidence_for_a_local_helper(self):
                self._assert_named_but_silent()

            def test_unreachable_helper_assert(self):
                self._dead_assert()

            def test_constant_false_helper_assert(self):
                self._false_branch()

            def test_other_class_method(self):
                self._owned_elsewhere()

            def test_module_noop(self):
                _module_noop(1)

            def test_two_hops_is_not_one_hop(self):
                _module_two_hop()

            def test_nested_def_never_runs(self):
                def inner():
                    assert True

            def test_self_call_does_not_reach_module_function(self):
                self._module_inner()
        """,
    )
    relative = "tests/test_bad_helpers.py"
    assert _flagged(tmp_path) == {
        (relative, name)
        for name in (
            "test_uncalled",
            "test_called_after_return",
            "test_non_asserting",
            "test_name_is_not_evidence_for_a_local_helper",
            "test_unreachable_helper_assert",
            "test_constant_false_helper_assert",
            "test_other_class_method",
            "test_module_noop",
            "test_two_hops_is_not_one_hop",
            "test_nested_def_never_runs",
            "test_self_call_does_not_reach_module_function",
        )
    }


def test_direct_assertions_after_return_are_not_evidence(tmp_path: Path):
    _write(
        tmp_path,
        "tests/test_dead.py",
        """
        def test_dead_assert():
            return None
            assert True

        def test_conditional_return_keeps_later_assert():
            if flag():
                return None
            assert True
        """,
    )
    assert _flagged(tmp_path) == {("tests/test_dead.py", "test_dead_assert")}


def _run_cli(root: Path):
    import subprocess

    return subprocess.run(
        [sys.executable, str(FIXER_PATH), str(root)], capture_output=True, text=True, check=False, timeout=60
    )


def test_cli_fails_on_an_assertion_free_test(tmp_path: Path):
    _write(tmp_path, "tests/test_weak.py", _EMPTY_TEST)
    result = _run_cli(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "test_empty" in result.stdout


def test_cli_passes_on_helper_backed_tests(tmp_path: Path):
    _write(
        tmp_path,
        "tests/test_good.py",
        """
        class TestCron:
            def _run_twice(self):
                self.assertTrue(run())

            def test_twice(self):
                self._run_twice()
        """,
    )
    result = _run_cli(tmp_path)
    assert result.returncode == 0, result.stdout


def test_ci_static_checks_consume_the_exit_code():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'run_check "Weak test detection"     python3 ci/weak_test_fixer.py' in workflow
    assert 'run_advisory "Weak test detection"' not in workflow


def test_repository_has_no_assertion_free_tests():
    assert _run_cli(ROOT).returncode == 0

# conftest.py - pytest configuration for tests/
#
# When the Odoo framework is not importable (a plain `pytest` run, e.g. the CI
# "pure-python" tier and local `make pr-check`/`make test`), every test
# module that imports Odoo is automatically deactivated. Those tests run under
# `odoo --test-enable` (Odoo.sh runtime), never in the pure-python environment.
#
# Detection is automatic (scan for an `import odoo` / `from odoo` line) so the
# pure-python set stays in sync without a hand-maintained allowlist that drifts
# whenever an Odoo test is added or renamed.

import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _line_names_odoo_module(line: str) -> bool:
    """True for ``import odoo`` / ``from odoo``, not ``import odools_...``."""
    stripped = line.lstrip()
    for keyword in ("import ", "from "):
        if not stripped.startswith(keyword):
            continue
        rest = stripped[len(keyword) :].lstrip()
        token = rest.split(" ", 1)[0].split(".", 1)[0].rstrip(",")
        return token == "odoo"
    return False


def _imports_odoo(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if _line_names_odoo_module(line):
                    return True
    except OSError:
        return False
    return False


def _collect_odoo_test_files() -> list[str]:
    ignored = []
    for dirpath, _dirs, files in os.walk(_HERE):
        for name in files:
            if not name.endswith(".py") or name == "conftest.py":
                continue
            full = os.path.join(dirpath, name)
            if _imports_odoo(full):
                ignored.append(os.path.relpath(full, _HERE))
    return ignored


def _odoo_available() -> bool:
    try:
        return importlib.util.find_spec("odoo") is not None
    except (ImportError, ValueError):
        return False


# Deactivate Odoo-dependent tests when the Odoo framework isn't installed.
if not _odoo_available():
    collect_ignore = _collect_odoo_test_files()


# Mandatory portable contracts are ordinary pytest tests, not another test run.
# Odoo-only tests retain the existing collection policy above.

_CONTRACT_STATE = pytest.StashKey[dict[str, set[str]]]()
_NIGHTLY_TIER = "nightly_full"
_PR_FAST_TIER = "pr_fast"
_ADMITTED_TIERS = {_NIGHTLY_TIER, _PR_FAST_TIER}
_PR_FAST_MARKERS = {"adversarial_contract", "not adversarial_contract"}
_NARROWING = ("keyword", "ignore", "ignore_glob", "deselect", "collectonly", "lf", "ff")


def _option_set(config, name: str) -> bool:
    value = getattr(config.option, name, None)
    if value is None or value is False:
        return False
    if isinstance(value, (list, tuple)):
        return any(value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _repo_has_contract_tree() -> bool:
    return os.path.isfile(os.path.join(os.getcwd(), "tests", "conftest.py"))


def _enforce_contract_tier(config) -> None:
    if os.environ.get("PYTEST_ADDOPTS"):
        raise pytest.UsageError("Required CI may not honor PYTEST_ADDOPTS")
    if os.environ.get("PLASTICOS_SMOKE_SOURCE"):
        raise pytest.UsageError("Required CI must exercise checkout source, not a calibration donor")
    tier = os.environ.get("PLASTICOS_CI_TIER", "")
    if tier not in _ADMITTED_TIERS:
        raise pytest.UsageError("PLASTICOS_CONTRACT_CI=1 requires PLASTICOS_CI_TIER=pr_fast or nightly_full")
    markexpr = str(getattr(config.option, "markexpr", None) or "").strip()
    if tier == _NIGHTLY_TIER:
        _enforce_nightly(config, markexpr)
        return
    _enforce_pr_fast(config, markexpr)


def _enforce_nightly(config, markexpr: str) -> None:
    if markexpr or any(_option_set(config, name) for name in _NARROWING):
        raise pytest.UsageError("Nightly full tier may not narrow the suite")
    if not _repo_has_contract_tree():
        return
    args = [str(arg) for arg in (config.args or [])]
    if args not in ([], ["tests"], ["tests/"]):
        raise pytest.UsageError("Nightly full tier must collect tests/ with no selector")


def _enforce_pr_fast(config, markexpr: str) -> None:
    for name in _NARROWING:
        if _option_set(config, name):
            raise pytest.UsageError(f"Required CI may not narrow the full test tier: {name}")
    if markexpr not in _PR_FAST_MARKERS:
        raise pytest.UsageError("pr_fast admits only -m adversarial_contract or -m 'not adversarial_contract'")
    args = [str(arg) for arg in (config.args or [])]
    if markexpr == "adversarial_contract":
        _enforce_pr_fast_marker(args)
        return
    if not args or any(_unsafe_scoped_arg(arg) for arg in args):
        raise pytest.UsageError("pr_fast scoped selection requires explicit test modules")


def _enforce_pr_fast_marker(args: list[str]) -> None:
    if any(arg.endswith(".py") for arg in args) or len(args) > 1:
        raise pytest.UsageError("pr_fast mandatory selection must cover the tests tree, not a file list")
    if _repo_has_contract_tree() and args not in (["tests"], ["tests/"]):
        raise pytest.UsageError("pr_fast mandatory selection must be tests/")


def _unsafe_scoped_arg(arg: str) -> bool:
    path = arg.replace("\\", "/")
    return not path.endswith(".py") or ".." in path.split("/") or path.rstrip("/") in {"tests", "tests/"}


def pytest_configure(config):
    config.addinivalue_line("markers", "adversarial_contract: portable safety contract; skips and xfails are failures")
    config.stash[_CONTRACT_STATE] = {"collected": set(), "passed": set(), "deselected": set()}
    if os.environ.get("PLASTICOS_CONTRACT_CI") == "1":
        _enforce_contract_tier(config)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    config.stash[_CONTRACT_STATE]["collected"].update(
        item.nodeid for item in items if item.get_closest_marker("adversarial_contract")
    )


def pytest_deselected(items):
    for item in items:
        if item.get_closest_marker("adversarial_contract"):
            item.config.stash[_CONTRACT_STATE]["deselected"].add(item.nodeid)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not item.get_closest_marker("adversarial_contract"):
        return
    report.user_properties.append(("contract_tier", "adversarial_contract"))
    if report.skipped or hasattr(report, "wasxfail"):
        report.outcome = "failed"
        report.longrepr = (
            str(item.path),
            item.location[1],
            "Mandatory adversarial contract did not execute successfully (skip/xfail is not proof)",
        )
        if hasattr(report, "wasxfail"):
            del report.wasxfail
    if report.when == "call" and report.passed:
        item.config.stash[_CONTRACT_STATE]["passed"].add(item.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("PLASTICOS_CONTRACT_CI") != "1":
        return
    state = session.config.stash[_CONTRACT_STATE]
    tier = os.environ.get("PLASTICOS_CI_TIER", "")
    markexpr = str(getattr(session.config.option, "markexpr", None) or "").strip()
    if tier == _PR_FAST_TIER and markexpr == "not adversarial_contract":
        if state["collected"]:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            if reporter:
                reporter.write_line("Scoped lane executed a mandatory adversarial contract")
        return
    missing = state["collected"] - state["passed"]
    if not state["collected"] or missing or state["deselected"]:
        if session.exitstatus in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_sep("=", "Mandatory contract coverage incomplete")
            reporter.write_line(
                f"collected={len(state['collected'])}, passed={len(state['passed'])}, "
                f"deselected={len(state['deselected'])}"
            )
            for nodeid in sorted(missing | state["deselected"]):
                reporter.write_line(nodeid)

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


def _imports_odoo(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.lstrip()
                if stripped.startswith(("import odoo", "from odoo")):
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


def pytest_configure(config):
    config.addinivalue_line("markers", "adversarial_contract: portable safety contract; skips and xfails are failures")
    config.stash[_CONTRACT_STATE] = {"collected": set(), "passed": set(), "deselected": set()}
    if os.environ.get("PLASTICOS_CONTRACT_CI") == "1":
        if os.environ.get("PLASTICOS_SMOKE_SOURCE"):
            raise pytest.UsageError("Required CI must exercise checkout source, not a calibration donor")
        for option in ("keyword", "markexpr", "ignore", "ignore_glob", "deselect", "collectonly", "lf", "ff"):
            if getattr(config.option, option, None):
                raise pytest.UsageError(f"Required CI may not narrow the full test tier: {option}")


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
    missing = state["collected"] - state["passed"]
    if not state["collected"] or missing or state["deselected"]:
        if session.exitstatus == pytest.ExitCode.OK:
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

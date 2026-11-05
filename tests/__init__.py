# Central test pack for cross-module integration tests.
#
# Odoo imports the package when the test pack is loaded; a plain `pytest` run does
# not (tests/conftest.py collect-ignores every Odoo-importing module instead). Both
# paths must tolerate a missing Odoo runtime, so imports are soft.
#
# Module discovery is by filesystem scan, NOT a hand-maintained list. The previous
# hardcoded _ODOO_TEST_MODULES / _PURE_PYTHON_MODULES pair had drifted badly: it
# named 24 of the 47 modules actually present, and listed one file
# (test_gate_matcher_fallback) that no longer exists. A list that must be edited
# whenever a test is added will drift again; a scan cannot.

import importlib
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SUBPACKAGES = ("contracts", "integration")


def _module_names() -> list[str]:
    """Every test_*.py directly in this package, sorted."""
    return sorted(name[:-3] for name in os.listdir(_HERE) if name.startswith("test_") and name.endswith(".py"))


def _try_import(module_name: str) -> bool:
    """Import a submodule, returning False when its dependencies are unavailable.

    Odoo-backed test modules raise ImportError under a pure-Python harness; that is
    expected and non-fatal. NameError/AttributeError are also swallowed because a
    partially-loaded Odoo registry can surface either.
    """
    try:
        importlib.import_module(f".{module_name}", __name__)
        return True
    except (ImportError, NameError, AttributeError):
        return False


for _mod in _module_names():
    _try_import(_mod)

for _pkg in _SUBPACKAGES:
    _try_import(_pkg)

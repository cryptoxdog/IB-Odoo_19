# conftest.py - pytest configuration for tests/
#
# When the Odoo framework is not importable (a plain `pytest` run, e.g. the CI
# "pure-python" tier and local `make pr-check`/`make test-pure`), every test
# module that imports Odoo is automatically deactivated. Those tests run under
# `odoo --test-enable` (Odoo.sh runtime), never in the pure-python environment.
#
# Detection is automatic (scan for an `import odoo` / `from odoo` line) so the
# pure-python set stays in sync without a hand-maintained allowlist that drifts
# whenever an Odoo test is added or renamed.

import importlib.util
import os

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

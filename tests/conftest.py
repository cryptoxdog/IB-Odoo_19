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


# ── Odoo-free access to addon service layers ────────────────────────────────
#
# `plasticos_gate/services/*` is deliberately framework-free so its contracts
# (builders, mappers, projection, retry policy) can be tested without an Odoo
# runtime. Importing `plasticos_gate.services.X` normally executes the addon's
# `__init__.py`, which imports `models` and therefore `odoo` — so as soon as the
# addon gained an ORM model, every pure-python contract test broke on an import
# it never actually needed.
#
# Registering the package and subpackage as bare namespaces bound to the real
# directories lets submodule and relative imports resolve while skipping the
# addon `__init__.py`. This exposes the service layer only; nothing here stubs,
# fakes, or weakens `odoo` itself, and Odoo-importing tests stay deactivated by
# the collect_ignore logic above.

_ODOO_FREE_SERVICE_PACKAGES = {
    "plasticos_gate": ("services",),
}


def _register_service_namespaces() -> None:
    import sys
    import types

    repo_root = os.path.dirname(_HERE)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    for addon, subpackages in _ODOO_FREE_SERVICE_PACKAGES.items():
        addon_path = os.path.join(repo_root, addon)
        if not os.path.isdir(addon_path) or addon in sys.modules:
            continue
        package = types.ModuleType(addon)
        package.__path__ = [addon_path]
        sys.modules[addon] = package
        for sub in subpackages:
            sub_path = os.path.join(addon_path, sub)
            if not os.path.isdir(sub_path):
                continue
            sub_module = types.ModuleType(f"{addon}.{sub}")
            sub_module.__path__ = [sub_path]
            sys.modules[f"{addon}.{sub}"] = sub_module
            setattr(package, sub, sub_module)


if not _odoo_available():
    _register_service_namespaces()

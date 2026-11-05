"""Odoo runtime tests must live where the Odoo 19 test loader can find them.

Odoo 19 (``odoo/tests/loader.py``) collects tests for an addon from exactly one
place: the members named ``test_*`` of the package ``odoo.addons.<addon>.tests``.
``inspect.getmembers`` only sees submodules that package has imported, so a test
file is discovered only when the addon's ``tests/__init__.py`` imports it.
``--test-file`` / ``--test-tags`` filter that collected set; they never add to it.

Until 2026-10 the repository-root ``tests/`` tree held 39 Odoo-backed modules
(``PlasticosTestCase`` / ``TransactionCase``). ``tests/conftest.py`` collect-ignores
them under pytest, and the Odoo loader never looks outside addon test packages,
so they ran nowhere. They now live in their owning addon's ``tests/`` package.
These checks keep it that way. They are static: no Odoo runtime is needed.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"


def _imports_odoo(path: Path) -> bool:
    """True when the module imports ``odoo`` at any level (same rule as conftest.py)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "odoo" or a.name.startswith("odoo.") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            mod = node.module or ""
            if mod == "odoo" or mod.startswith("odoo."):
                return True
    return False


def _package_imports(init_file: Path) -> set[str]:
    """Submodule names a package ``__init__.py`` imports via ``from . import x``."""
    names: set[str] = set()
    tree = ast.parse(init_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and not node.module:
            names.update(alias.name for alias in node.names)
    return names


def _addon_test_dirs() -> list[Path]:
    return sorted(p for p in ROOT.glob("plasticos_*/tests") if p.is_dir() and any(p.glob("test_*.py")))


class TestOdooTestDiscovery:
    def test_root_tests_tree_holds_no_odoo_test_module(self):
        """A test_*.py under tests/ that imports odoo is run by neither pytest nor Odoo."""
        orphans = sorted(
            str(p.relative_to(ROOT))
            for p in TESTS_DIR.rglob("test_*.py")
            if "__pycache__" not in p.parts and _imports_odoo(p)
        )
        assert not orphans, (
            "Odoo-backed test modules under tests/ are never executed: conftest.py "
            "collect-ignores them and the Odoo loader only reads addon test packages. "
            "Move each into its owning addon's tests/ package and import it from that "
            "package's __init__.py:\n  " + "\n  ".join(orphans)
        )

    def test_addon_test_packages_have_init(self):
        missing = [str(d.relative_to(ROOT)) for d in _addon_test_dirs() if not (d / "__init__.py").is_file()]
        assert not missing, "Addon tests/ directories without __init__.py are not packages:\n  " + "\n  ".join(missing)

    def test_every_addon_test_module_is_imported_by_its_package(self):
        """The loader sees only submodules the tests package imported."""
        unimported = []
        for tests_dir in _addon_test_dirs():
            init_file = tests_dir / "__init__.py"
            if not init_file.is_file():
                continue
            imported = _package_imports(init_file)
            unimported.extend(
                str(f.relative_to(ROOT)) for f in sorted(tests_dir.glob("test_*.py")) if f.stem not in imported
            )
        assert not unimported, (
            "Addon test modules not imported by tests/__init__.py are never run by Odoo:\n  " + "\n  ".join(unimported)
        )

    def test_addon_test_package_imports_resolve(self):
        """Every ``from . import x`` in an addon tests package names a real module."""
        dangling = []
        for tests_dir in _addon_test_dirs():
            init_file = tests_dir / "__init__.py"
            if not init_file.is_file():
                continue
            for name in sorted(_package_imports(init_file)):
                if not ((tests_dir / f"{name}.py").is_file() or (tests_dir / name / "__init__.py").is_file()):
                    dangling.append(f"{init_file.relative_to(ROOT)}: {name}")
        assert not dangling, "tests/__init__.py imports a module that does not exist:\n  " + "\n  ".join(dangling)

#!/usr/bin/env python3
"""

Odoo Module Dependency Wiring Checker

Ensures all Odoo modules are properly wired to the modules they depend on.

Checks performed:
1. DEPENDENCY WIRING: Model references match declared dependencies in __manifest__.py
2. IMPORT WIRING: All .py files in models/ are imported in models/__init__.py
3. MODULE INIT WIRING: models/__init__.py is imported in module __init__.py
4. FILE EXISTENCE: All imported modules actually exist

Run: python3 scripts/check_module_wiring.py [module_name]
     python3 scripts/check_module_wiring.py  # checks all modules
     python3 scripts/check_module_wiring.py plasticos_facility_profile  # single module

Exit codes:
  0 = All checks passed
  1 = Wiring errors found
"""

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

MODELS_INIT = "models/__init__.py"
INIT_FILE = "__init__.py"
PLASTICOS_GLOB = "plasticos_*"
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"


def get_git_tracked_files(pattern: str = "") -> list[Path]:
    """Get git-tracked files matching pattern."""
    try:
        cmd = ["git", "ls-files"]
        if pattern:
            cmd.append(pattern)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [Path(f) for f in result.stdout.strip().split("\n") if f]
    except subprocess.CalledProcessError:
        return []


def get_git_tracked_dirs(pattern: str = PLASTICOS_GLOB) -> list[Path]:
    """Get git-tracked directories matching pattern."""
    try:
        result = subprocess.run(
            ["git", "ls-files", f"{pattern}/*"],
            capture_output=True,
            text=True,
            check=True,
        )
        dirs = set()
        for f in result.stdout.strip().split("\n"):
            if f and "/" in f:
                parts = f.split("/")
                if parts[0].startswith(pattern.replace("*", "")):
                    dirs.add(Path(parts[0]))
        return sorted(dirs)
    except subprocess.CalledProcessError:
        return []


# ANSI colors
NC = "\033[0m"  # No Color

# Core Odoo modules that provide standard models
CORE_ODOO_MODULES = {
    "base": [
        "res.partner",
        "res.users",
        "res.company",
        "res.country",
        "res.country.state",
        "res.currency",
        "res.lang",
        "res.groups",
        "res.config.settings",
        "ir.model",
        "ir.model.fields",
        "ir.model.access",
        "ir.rule",
        "ir.sequence",
        "ir.attachment",
        "ir.cron",
        "ir.actions.act_window",
        "ir.actions.server",
        "ir.ui.view",
        "ir.ui.menu",
        "ir.module.module",
        "ir.default",
        "ir.property",
        "ir.filters",
        "ir.exports",
        "ir.exports.line",
    ],
    "mail": [
        "mail.thread",
        "mail.activity.mixin",
        "mail.message",
        "mail.activity",
        "mail.activity.type",
        "mail.followers",
        "mail.template",
        "mail.mail",
        "mail.channel",
        "mail.alias",
    ],
    "contacts": [],  # Extends res.partner, no new models
    "sale": [
        "sale.order",
        "sale.order.line",
        "sale.order.template",
        "sale.order.template.line",
    ],
    "sale_management": [
        "sale.order",
        "sale.order.line",
    ],
    "purchase": [
        "purchase.order",
        "purchase.order.line",
    ],
    "stock": [
        "stock.picking",
        "stock.move",
        "stock.move.line",
        "stock.location",
        "stock.warehouse",
        "stock.quant",
        "stock.lot",
        "product.product",
        "product.template",
    ],
    "product": [
        "product.product",
        "product.template",
        "product.category",
        "product.pricelist",
        "product.pricelist.item",
        "uom.uom",
        "uom.category",
    ],
    "account": [
        "account.move",
        "account.move.line",
        "account.account",
        "account.journal",
        "account.tax",
        "account.payment",
        "account.payment.term",
    ],
    "crm": [
        "crm.lead",
        "crm.stage",
        "crm.team",
        "crm.tag",
    ],
    "website": [
        "website",
        "website.page",
        "website.menu",
        "website.visitor",
    ],
    "hr": [
        "hr.employee",
        "hr.department",
        "hr.job",
    ],
}


def parse_manifest(module_path: Path) -> dict[str, Any] | None:
    """Parse __manifest__.py and return its contents."""
    manifest_path = module_path / "__manifest__.py"
    if not manifest_path.exists():
        return None

    try:
        content = manifest_path.read_text()
        # Use ast.literal_eval for safe parsing
        return ast.literal_eval(content)
    except (SyntaxError, ValueError) as e:
        print(f"{YELLOW}Warning: Could not parse {manifest_path}: {e}{NC}")
        return None


def find_model_definitions(module_path: Path) -> dict[str, str]:
    """
    Find all model definitions in a module.
    Returns dict mapping model name -> file path.
    """
    models: dict[str, str] = {}
    models_dir = module_path / "models"

    if not models_dir.exists():
        return models

    for py_file in models_dir.glob("*.py"):
        if py_file.name == INIT_FILE:
            continue

        try:
            content = py_file.read_text()
            # Match _name = "model.name" patterns
            name_matches = re.findall(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            for model_name in name_matches:
                models[model_name] = str(py_file)
            # Also resolve _name = CONSTANT where CONSTANT = "model.name" (e.g. plasticos_transaction)
            constants = dict(re.findall(r'([A-Z][A-Z0-9_]+)\s*=\s*["\']([a-z][a-z0-9_.]+)["\']', content))
            for const in re.findall(r'_name\s*=\s*([A-Z][A-Z0-9_]+)', content):
                if const in constants:
                    models[constants[const]] = str(py_file)
        except Exception:
            continue

    return models


def find_model_references(module_path: Path) -> dict[str, list[tuple[str, int, str]]]:
    """
    Find all model references in a module's Python files.
    Returns dict mapping model name -> list of (file, line_number, context).
    """
    references: dict[str, list[tuple[str, int, str]]] = {}
    models_dir = module_path / "models"

    if not models_dir.exists():
        return references

    # Single-line patterns
    line_patterns = [
        # comodel_name parameter
        (r'comodel_name\s*=\s*["\']([^"\']+)["\']', "comodel_name"),
        # _inherit = "model.name"
        (r'_inherit\s*=\s*["\']([^"\']+)["\']', "_inherit"),
        # _inherit = ["model1", "model2"]
        (r"_inherit\s*=\s*\[([^\]]+)\]", "_inherit list"),
        # _inherits = {"model": "field"}
        (r'_inherits\s*=\s*\{["\']([^"\']+)["\']', "_inherits"),
        (r'self\.env\s*\[\s*["\']([^"\']+)["\']', "env reference"),
    ]

    # Multiline patterns (for field definitions that span lines)
    # These are applied to the full file content
    multiline_patterns = [
        # Many2one, Many2many, One2many - model name on same or next line
        (
            r'fields\.(?:Many2one|Many2many|One2many)\s*\(\s*["\']([a-z_.]+)["\']',
            "relational field",
        ),
    ]

    for py_file in models_dir.glob("*.py"):
        try:
            content = py_file.read_text()
            lines = content.split("\n")

            # Apply line-by-line patterns
            for line_num, line in enumerate(lines, 1):
                for pattern, context in line_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        # Handle list patterns (e.g., _inherit = ["a", "b"])
                        if context == "_inherit list":
                            # Extract individual model names from the list
                            model_names = re.findall(r'["\']([^"\']+)["\']', match)
                            for model_name in model_names:
                                if model_name not in references:
                                    references[model_name] = []
                                references[model_name].append((str(py_file), line_num, context))
                        else:
                            if match not in references:
                                references[match] = []
                            references[match].append((str(py_file), line_num, context))

            # Apply multiline patterns to full content
            for pattern, context in multiline_patterns:
                for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                    model_name = match.group(1)
                    # Find line number
                    line_num = content[: match.start()].count("\n") + 1
                    if model_name not in references:
                        references[model_name] = []
                    references[model_name].append((str(py_file), line_num, context))

        except Exception:
            continue

    return references


def build_model_registry(workspace: Path) -> dict[str, str]:
    """
    Build a registry mapping model names to their providing modules.
    Includes both core Odoo modules and custom plasticos_* modules.
    """
    registry: dict[str, str] = {}

    # Add core Odoo models
    for module, models in CORE_ODOO_MODULES.items():
        for model in models:
            registry[model] = module

    # Scan custom modules (git-tracked only)
    module_dirs = get_git_tracked_dirs(PLASTICOS_GLOB)
    if not module_dirs:
        # Fallback if not in git repo
        module_dirs = [d for d in workspace.glob(PLASTICOS_GLOB) if d.is_dir()]

    for module_dir in module_dirs:
        module_dir = workspace / module_dir if not module_dir.is_absolute() else module_dir
        if not module_dir.is_dir():
            continue

        module_name = module_dir.name
        models = find_model_definitions(module_dir)

        for model_name in models:
            # Don't override core Odoo models - custom modules may extend them
            # via _inherit + _name but the base model is still from core
            if model_name not in registry:
                registry[model_name] = module_name

    return registry


def get_transitive_dependencies(
    module_name: str,
    all_manifests: dict[str, dict],
    visited: set[str] | None = None,
) -> set[str]:
    """
    Get all transitive dependencies for a module.
    """
    if visited is None:
        visited = set()

    if module_name in visited:
        return set()

    visited.add(module_name)
    deps = set()

    manifest = all_manifests.get(module_name)
    if manifest:
        direct_deps = manifest.get("depends", [])
        deps.update(direct_deps)
        for dep in direct_deps:
            deps.update(get_transitive_dependencies(dep, all_manifests, visited))

    return deps


def check_init_imports(module_path: Path) -> list[dict]:
    """
    Check that all Python files in models/ are imported in models/__init__.py
    and that models/__init__.py is imported in the module's __init__.py.
    Returns list of wiring errors.
    """
    errors: list[dict] = []
    module_name = module_path.name

    models_dir = module_path / "models"
    models_init = models_dir / INIT_FILE
    module_init = module_path / INIT_FILE

    # Check 1: Module __init__.py exists and imports models
    if module_init.exists():
        module_init_content = module_init.read_text()
        # Check for "from . import models" or "from .models import"
        has_models_import = bool(
            re.search(r"from\s+\.\s+import\s+models", module_init_content)
            or re.search(r"from\s+\.models\s+import", module_init_content)
            or re.search(r"import\s+models", module_init_content)
        )

        if models_dir.exists() and not has_models_import:
            errors.append(
                {
                    "type": "missing_models_import",
                    "module": module_name,
                    "file": str(module_init),
                    "line": 1,
                    "context": "module __init__.py",
                    "message": (
                        f"Module '{module_name}/__init__.py' does not import 'models'. Add: from . import models"
                    ),
                }
            )
    else:
        if models_dir.exists():
            errors.append(
                {
                    "type": "missing_module_init",
                    "module": module_name,
                    "file": str(module_init),
                    "line": 1,
                    "context": "module __init__.py",
                    "message": f"Module '{module_name}' is missing __init__.py",
                }
            )

    # Check 2: All .py files in models/ are imported in models/__init__.py
    if not models_dir.exists():
        return errors

    if not models_init.exists():
        # models/ exists but no __init__.py
        py_files = list(models_dir.glob("*.py"))
        if py_files:
            errors.append(
                {
                    "type": "missing_models_init",
                    "module": module_name,
                    "file": str(models_init),
                    "line": 1,
                    "context": MODELS_INIT,
                    "message": (f"Module '{module_name}/models/' has Python files but no __init__.py"),
                }
            )
        return errors

    # Parse models/__init__.py to find imports
    init_content = models_init.read_text()

    # Find all "from . import X" statements
    imported_modules: set[str] = set()
    for match in re.finditer(r"from\s+\.\s+import\s+(\w+)", init_content):
        imported_modules.add(match.group(1))

    # Also check for "from .X import" patterns
    for match in re.finditer(r"from\s+\.(\w+)\s+import", init_content):
        imported_modules.add(match.group(1))

    # Find all .py files in models/ (excluding __init__.py)
    py_files = [f.stem for f in models_dir.glob("*.py") if f.name != INIT_FILE and not f.name.startswith("_")]

    # Check for missing imports
    for py_file in py_files:
        if py_file not in imported_modules:
            errors.append(
                {
                    "type": "missing_model_import",
                    "module": module_name,
                    "file": str(models_init),
                    "line": 1,
                    "context": MODELS_INIT,
                    "missing_import": py_file,
                    "message": (
                        f"File '{module_name}/models/{py_file}.py' exists but is not "
                        f"imported in models/__init__.py. Add: from . import {py_file}"
                    ),
                }
            )

    # Check for imports that don't have corresponding files
    for imported in imported_modules:
        expected_file = models_dir / f"{imported}.py"
        if not expected_file.exists():
            # Find the line number of the import
            line_num = 1
            for i, line in enumerate(init_content.split("\n"), 1):
                if f"import {imported}" in line:
                    line_num = i
                    break

            errors.append(
                {
                    "type": "dangling_import",
                    "module": module_name,
                    "file": str(models_init),
                    "line": line_num,
                    "context": MODELS_INIT,
                    "dangling_import": imported,
                    "message": (
                        f"models/__init__.py imports '{imported}' but "
                        f"'{module_name}/models/{imported}.py' does not exist"
                    ),
                }
            )

    return errors


def check_module_wiring(
    module_path: Path,
    model_registry: dict[str, str],
    all_manifests: dict[str, dict],
) -> list[dict]:
    """
    Check if a module is properly wired to its dependencies.
    Returns list of wiring errors.
    """
    errors: list[dict] = []
    module_name = module_path.name

    manifest = parse_manifest(module_path)
    if not manifest:
        return errors

    # Check 1: Init file wiring
    init_errors = check_init_imports(module_path)
    errors.extend(init_errors)

    # Check 2: Dependency wiring
    # Get declared dependencies (including transitive)
    declared_deps = set(manifest.get("depends", []))
    transitive_deps = get_transitive_dependencies(module_name, all_manifests)
    all_deps = declared_deps | transitive_deps | {module_name}  # Include self

    # Find model references
    references = find_model_references(module_path)

    # Check each reference
    for model_name, locations in references.items():
        providing_module = model_registry.get(model_name)

        if providing_module is None:
            # Unknown model - might be defined elsewhere or typo
            # Only warn if it looks like a plasticos model
            if model_name.startswith("plasticos."):
                for file_path, line_num, context in locations:
                    errors.append(
                        {
                            "type": "unknown_model",
                            "module": module_name,
                            "model": model_name,
                            "file": file_path,
                            "line": line_num,
                            "context": context,
                            "message": f"Unknown model '{model_name}' - not found in any module",
                        }
                    )
            continue

        # Check if the providing module is in dependencies
        if providing_module not in all_deps:
            for file_path, line_num, context in locations:
                errors.append(
                    {
                        "type": "missing_dependency",
                        "module": module_name,
                        "model": model_name,
                        "providing_module": providing_module,
                        "file": file_path,
                        "line": line_num,
                        "context": context,
                        "declared_deps": list(declared_deps),
                        "message": (
                            f"Module '{module_name}' references model '{model_name}' "
                            f"from '{providing_module}' but does not declare it as a dependency"
                        ),
                    }
                )

    return errors


def main() -> int:
    """Main entry point."""
    workspace = Path(__file__).parent.parent

    # Determine which modules to check
    target_module = sys.argv[1] if len(sys.argv) > 1 else None

    print(f"{CYAN}🔌 Odoo Module Dependency Wiring Checker{NC}")
    print("=" * 50)
    print()

    # Build model registry
    print("Building model registry...")
    model_registry = build_model_registry(workspace)
    print(f"  Found {len(model_registry)} models across all modules")
    print()

    # Load all manifests for transitive dependency resolution (git-tracked only)
    all_manifests: dict[str, dict] = {}
    module_dirs = get_git_tracked_dirs(PLASTICOS_GLOB)
    if not module_dirs:
        module_dirs = [d for d in workspace.glob(PLASTICOS_GLOB) if d.is_dir()]

    for module_dir in module_dirs:
        module_dir = workspace / module_dir if not module_dir.is_absolute() else module_dir
        if module_dir.is_dir():
            manifest = parse_manifest(module_dir)
            if manifest:
                all_manifests[module_dir.name] = manifest

    # Add core module stubs for dependency resolution
    for core_module in CORE_ODOO_MODULES:
        if core_module not in all_manifests:
            all_manifests[core_module] = {"depends": ["base"] if core_module != "base" else []}

    # Find modules to check (git-tracked only)
    if target_module:
        module_path = workspace / target_module
        if not module_path.exists():
            print(f"{RED}Error: Module '{target_module}' not found{NC}")
            return 1
        modules_to_check = [module_path]
    else:
        module_dirs = get_git_tracked_dirs(PLASTICOS_GLOB)
        if module_dirs:
            modules_to_check = sorted([workspace / d for d in module_dirs])
        else:
            # Fallback if not in git repo
            modules_to_check = sorted([d for d in workspace.glob(PLASTICOS_GLOB) if d.is_dir()])

    # Check each module
    all_errors: list[dict] = []
    modules_checked = 0

    for module_path in modules_to_check:
        module_name = module_path.name
        manifest = parse_manifest(module_path)

        if not manifest:
            continue

        modules_checked += 1
        errors = check_module_wiring(module_path, model_registry, all_manifests)

        if errors:
            all_errors.extend(errors)
            print(f"{RED}✗ {module_name}{NC}")
            for error in errors:
                rel_file = Path(error["file"]).relative_to(workspace)
                print(f"  {YELLOW}Line {error['line']}{NC}: {rel_file}")
                print(f"    {error['message']}")
                if error["type"] == "missing_dependency":
                    print(f"    {CYAN}Fix: Add '{error['providing_module']}' to 'depends' in __manifest__.py{NC}")
                print()
        else:
            print(f"{GREEN}✓ {module_name}{NC}")

    # Summary
    print()
    print("=" * 50)
    print(f"Modules checked: {modules_checked}")

    if all_errors:
        # Group errors by type
        missing_deps = [e for e in all_errors if e["type"] == "missing_dependency"]
        unknown_models = [e for e in all_errors if e["type"] == "unknown_model"]
        missing_imports = [e for e in all_errors if e["type"] == "missing_model_import"]
        dangling_imports = [e for e in all_errors if e["type"] == "dangling_import"]
        missing_models_import = [e for e in all_errors if e["type"] == "missing_models_import"]
        missing_inits = [e for e in all_errors if e["type"] in ("missing_models_init", "missing_module_init")]

        print(f"{RED}❌ Found {len(all_errors)} wiring error(s):{NC}")
        if missing_deps:
            print(f"  - {len(missing_deps)} missing dependency declaration(s)")
        if unknown_models:
            print(f"  - {len(unknown_models)} unknown model reference(s)")
        if missing_imports:
            print(f"  - {len(missing_imports)} missing model import(s) in __init__.py")
        if dangling_imports:
            print(f"  - {len(dangling_imports)} dangling import(s) (file doesn't exist)")
        if missing_models_import:
            print(f"  - {len(missing_models_import)} module(s) not importing models package")
        if missing_inits:
            print(f"  - {len(missing_inits)} missing __init__.py file(s)")

        # Print fix summary
        print()
        print(f"{YELLOW}Fixes required:{NC}")

        # Dependency fixes
        fixes_by_module: dict[str, set[str]] = {}
        for error in missing_deps:
            module = error["module"]
            dep = error["providing_module"]
            if module not in fixes_by_module:
                fixes_by_module[module] = set()
            fixes_by_module[module].add(dep)

        for module, deps in sorted(fixes_by_module.items()):
            print(f"  {module}/__manifest__.py:")
            print(f"    Add to 'depends': {sorted(deps)}")

        # Import fixes
        import_fixes: dict[str, list[str]] = {}
        for error in missing_imports:
            module = error["module"]
            missing = error["missing_import"]
            if module not in import_fixes:
                import_fixes[module] = []
            import_fixes[module].append(missing)

        for module, imports in sorted(import_fixes.items()):
            print(f"  {module}/models/__init__.py:")
            for imp in sorted(imports):
                print(f"    Add: from . import {imp}")

        # Module init fixes
        for error in missing_models_import:
            print(f"  {error['module']}/__init__.py:")
            print("    Add: from . import models")

        return 1
    else:
        print(f"{GREEN}✅ All module wiring checks passed{NC}")
        return 0


if __name__ == "__main__":
    sys.exit(main())

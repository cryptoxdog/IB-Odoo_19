#!/usr/bin/env python3
"""
Circular Dependency & Cross-Module @api.depends Checker
========================================================

Prevents two common Odoo module errors:

1. CIRCULAR DEPENDENCIES: Module A depends on B, B depends on A
   - Causes: "Recursion error in modules dependencies!"

2. CROSS-MODULE @api.depends: Using fields from other modules in @api.depends
   - Causes: Field not found error at module load time
   - Correct pattern: Override compute method in bridge module

Usage:
    python3 ci/check_circular_deps.py [root_dir]

Exit codes:
    0 = No issues found
    1 = Issues found (blocks CI)
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path


def parse_manifest(manifest_path: Path) -> dict | None:
    """Parse __manifest__.py and return dict."""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            content = f.read()
        return ast.literal_eval(content)
    except Exception:
        return None


def get_module_dependencies(root_dir: Path) -> dict[str, set[str]]:
    """Build dependency graph: module_name -> set of dependencies."""
    deps = {}
    for manifest in root_dir.glob("*/__manifest__.py"):
        module_name = manifest.parent.name
        data = parse_manifest(manifest)
        if data and "depends" in data:
            deps[module_name] = set(data["depends"])
    return deps


def find_circular_deps(deps: dict[str, set[str]]) -> list[tuple[str, str]]:
    """Find direct circular dependencies (A -> B -> A)."""
    circular: list[tuple[str, str]] = []
    for module, module_deps in deps.items():
        for dep in module_deps:
            if dep in deps and module in deps[dep]:
                pair = (min(module, dep), max(module, dep))
                if pair not in circular:
                    circular.append(pair)
    return circular


def get_module_fields(root_dir: Path) -> dict[str, dict[tuple[str, str], str]]:
    """Map module_name -> {(model_name, field_name): file_path} for fields defined in that module."""
    module_fields: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)

    for py_file in root_dir.glob("*/models/*.py"):
        if "__pycache__" in str(py_file):
            continue
        module_name = py_file.parent.parent.name

        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        # Find model name (_name or _inherit)
        model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
        inherit_match = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', content)

        model_name = None
        if model_match:
            model_name = model_match.group(1)
        elif inherit_match:
            model_name = inherit_match.group(1)

        if not model_name:
            continue

        # Find field definitions
        for match in re.finditer(
            r"(\w+)\s*=\s*fields\.(Char|Integer|Float|Boolean|Date|Datetime|"
            r"Many2one|One2many|Many2many|Selection|Text|Html|Binary|Monetary|Reference|Image)",
            content,
        ):
            field_name = match.group(1)
            module_fields[module_name][(model_name, field_name)] = str(py_file)

    return module_fields


def check_cross_module_depends(
    root_dir: Path,
    deps: dict[str, set[str]],
    module_fields: dict[str, dict[str, str]],
) -> list[dict]:
    """Find @api.depends referencing fields from non-dependency modules."""
    errors = []

    for py_file in root_dir.glob("*/models/*.py"):
        if "__pycache__" in str(py_file):
            continue
        module_name = py_file.parent.parent.name

        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        # Find model being defined/inherited
        model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
        inherit_match = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', content)

        model_name = None
        if model_match:
            model_name = model_match.group(1)
        elif inherit_match:
            model_name = inherit_match.group(1)

        if not model_name:
            continue

        # Find @api.depends decorators
        for match in re.finditer(r"@api\.depends\(([^)]+)\)\s+def\s+(\w+)", content, re.MULTILINE):
            depends_args = match.group(1)
            method_name = match.group(2)
            field_names = re.findall(r'["\']([^"\']+)["\']', depends_args)

            for field_path in field_names:
                base_field = field_path.split(".")[0]

                # Skip magic fields
                if base_field in (
                    "id",
                    "create_uid",
                    "create_date",
                    "write_uid",
                    "write_date",
                    "display_name",
                    "__last_update",
                    "active",
                    "name",
                ):
                    continue

                # Check if field is defined in this module
                if (model_name, base_field) in module_fields.get(module_name, {}):
                    continue

                # Check if field is defined in a dependency module
                module_deps = deps.get(module_name, set())
                field_found_in_dep = False
                field_source_module = None

                for dep_module in module_deps:
                    if (model_name, base_field) in module_fields.get(dep_module, {}):
                        field_found_in_dep = True
                        break

                # Check ALL modules to find where field is defined
                for other_module, fields in module_fields.items():
                    if (model_name, base_field) in fields:
                        field_source_module = other_module
                        break

                if field_source_module and not field_found_in_dep:
                    # Field exists but in a module that's not a dependency
                    if field_source_module != module_name:
                        line_num = content[: match.start()].count("\n") + 1
                        errors.append(
                            {
                                "type": "CROSS_MODULE_DEPENDS",
                                "module": module_name,
                                "model": model_name,
                                "method": method_name,
                                "field": base_field,
                                "field_source": field_source_module,
                                "file": str(py_file),
                                "line": line_num,
                                "message": (
                                    f"@api.depends('{base_field}') in {module_name} references "
                                    f"field from {field_source_module} which is not a dependency. "
                                    f"Move the @api.depends to {field_source_module}'s bridge module."
                                ),
                            }
                        )

    return errors


def main():
    root_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

    print("🔍 Checking for circular dependencies...")
    deps = get_module_dependencies(root_dir)
    circular = find_circular_deps(deps)

    print("🔍 Checking for cross-module @api.depends violations...")
    module_fields = get_module_fields(root_dir)
    cross_module_errors = check_cross_module_depends(root_dir, deps, module_fields)

    # Report results
    errors = []

    if circular:
        print(f"\n❌ Found {len(circular)} circular dependencies:")
        for mod_a, mod_b in circular:
            print(f"   {mod_a} <-> {mod_b}")
            errors.append(
                {
                    "type": "CIRCULAR_DEPENDENCY",
                    "modules": [mod_a, mod_b],
                    "message": f"Circular dependency: {mod_a} <-> {mod_b}",
                    "fix": f"Remove one direction of the dependency between {mod_a} and {mod_b}",
                }
            )

    if cross_module_errors:
        print(f"\n❌ Found {len(cross_module_errors)} cross-module @api.depends violations:")
        for err in cross_module_errors:
            print(f"   {err['file']}:{err['line']}")
            print(f"      {err['message']}")
        errors.extend(cross_module_errors)

    if errors:
        print(f"\n{'=' * 60}")
        print(f"TOTAL ERRORS: {len(errors)}")
        print("=" * 60)
        print("\nThese errors will cause Odoo to fail at startup.")
        print("See scripts/audit/BASELINE.md for the correct pattern.")
        sys.exit(1)
    else:
        print("\n✅ No circular dependencies or cross-module @api.depends violations found!")
        sys.exit(0)


if __name__ == "__main__":
    main()

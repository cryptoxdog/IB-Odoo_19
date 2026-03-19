#!/usr/bin/env python3
"""
Cross-Module Dependency Audit
=============================

Scans all plasticos_* modules for model references that aren't declared
in the module's __manifest__.py depends list.

Detects the same root cause as the plasticos_commission → plasticos_transaction bug:
modules referencing models they don't depend on.

Usage:
    python3 ci/audit_cross_module_deps.py
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path


def parse_manifest(manifest_path: Path) -> dict:
    """Parse __manifest__.py and extract depends list."""
    try:
        content = manifest_path.read_text(encoding="utf-8", errors="replace")
        # Use ast.literal_eval for safe parsing
        manifest = ast.literal_eval(content)
        return {
            "depends": manifest.get("depends", []),
            "name": manifest.get("name", manifest_path.parent.name),
        }
    except Exception as e:
        return {"depends": [], "name": manifest_path.parent.name, "error": str(e)}


def extract_model_definitions(py_file: Path) -> list[tuple[int, str]]:
    """Extract _name = 'model.name' definitions from a Python file."""
    definitions = []
    try:
        content = py_file.read_text(encoding="utf-8", errors="replace")
        # Match _name = "model.name" or _name = 'model.name'
        pattern = r'_name\s*=\s*["\']([a-z_][a-z0-9_.]+)["\']'
        for match in re.finditer(pattern, content):
            line_num = content[: match.start()].count("\n") + 1
            definitions.append((line_num, match.group(1)))
    except Exception:
        pass
    return definitions


def extract_model_references(py_file: Path) -> list[tuple[int, str, str]]:
    """Extract model references from a Python file.

    Returns: list of (line_num, model_name, reference_type)
    """
    references = []
    try:
        content = py_file.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")

        patterns = [
            # self.env["model.name"] or self.env['model.name']
            (r'self\.env\s*\[\s*["\']([a-z_][a-z0-9_.]+)["\']\s*\]', "env[]"),
            # "model.name" in self.env
            (r'["\']([a-z_][a-z0-9_.]+)["\']\s+in\s+self\.env', "in env"),
            # fields.Many2one("model.name" or comodel_name="model.name"
            (r'fields\.Many2one\s*\(\s*["\']([a-z_][a-z0-9_.]+)["\']', "Many2one"),
            (r'comodel_name\s*=\s*["\']([a-z_][a-z0-9_.]+)["\']', "comodel_name"),
            # fields.One2many("model.name"
            (r'fields\.One2many\s*\(\s*["\']([a-z_][a-z0-9_.]+)["\']', "One2many"),
            # fields.Many2many("model.name"
            (r'fields\.Many2many\s*\(\s*["\']([a-z_][a-z0-9_.]+)["\']', "Many2many"),
            # _inherit = "model.name" or _inherit = ["model.name"]
            (r'_inherit\s*=\s*["\']([a-z_][a-z0-9_.]+)["\']', "_inherit"),
            (r'_inherit\s*=\s*\[["\']([a-z_][a-z0-9_.]+)["\']', "_inherit[]"),
        ]

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern, ref_type in patterns:
                for match in re.finditer(pattern, line):
                    model_name = match.group(1)
                    # Filter out common Odoo base models
                    if not model_name.startswith(("ir.", "res.", "base", "mail.", "bus.")):
                        references.append((line_num, model_name, ref_type))
    except Exception:
        pass
    return references


def build_model_to_module_map(root_dir: Path) -> dict[str, str]:
    """Build a map of model_name -> module_name for all plasticos_* modules."""
    model_map = {}

    for module_dir in root_dir.iterdir():
        if not module_dir.is_dir() or not module_dir.name.startswith("plasticos_"):
            continue

        models_dir = module_dir / "models"
        if not models_dir.exists():
            continue

        for py_file in models_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            for _, model_name in extract_model_definitions(py_file):
                model_map[model_name] = module_dir.name

    return model_map


def build_dependency_graph(root_dir: Path) -> dict[str, set[str]]:
    """Build a graph of module -> set of modules it depends on."""
    dep_graph = {}

    for module_dir in root_dir.iterdir():
        if not module_dir.is_dir() or not module_dir.name.startswith("plasticos_"):
            continue

        manifest_path = module_dir / "__manifest__.py"
        if not manifest_path.exists():
            continue

        manifest = parse_manifest(manifest_path)
        # Only track plasticos_* dependencies
        plasticos_deps = {d for d in manifest["depends"] if d.startswith("plasticos_")}
        dep_graph[module_dir.name] = plasticos_deps

    return dep_graph


def check_circular_dependency(dep_graph: dict[str, set[str]], from_module: str, to_module: str) -> bool:
    """Check if adding from_module -> to_module would create a circular dependency.

    Returns True if to_module already depends on from_module (directly or transitively).
    """
    visited = set()
    stack = [to_module]

    while stack:
        current = stack.pop()
        if current == from_module:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(dep_graph.get(current, set()))

    return False


def audit_module(module_dir: Path, model_map: dict[str, str], dep_graph: dict[str, set[str]]) -> list[dict]:
    """Audit a single module for undeclared dependencies."""
    issues: list[dict] = []
    module_name = module_dir.name

    manifest_path = module_dir / "__manifest__.py"
    if not manifest_path.exists():
        return issues

    manifest = parse_manifest(manifest_path)
    declared_deps = set(manifest["depends"])

    # Get models defined in this module
    models_defined = set()
    models_dir = module_dir / "models"
    if models_dir.exists():
        for py_file in models_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            for _, model_name in extract_model_definitions(py_file):
                models_defined.add(model_name)

    # Check all Python files in models/
    if models_dir.exists():
        for py_file in models_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            for line_num, model_name, ref_type in extract_model_references(py_file):
                # Skip if model is defined in this module
                if model_name in models_defined:
                    continue

                # Skip if model is not in our map (external/base model)
                if model_name not in model_map:
                    continue

                required_module = model_map[model_name]

                # Skip if it's the same module
                if required_module == module_name:
                    continue

                # Check if dependency is declared
                if required_module not in declared_deps:
                    # Check for circular dependency
                    would_be_circular = check_circular_dependency(dep_graph, module_name, required_module)

                    issues.append(
                        {
                            "module": module_name,
                            "file": str(py_file.relative_to(module_dir.parent)),
                            "line": line_num,
                            "model": model_name,
                            "ref_type": ref_type,
                            "required_module": required_module,
                            "circular": would_be_circular,
                        }
                    )

    # Also check tests/ directory
    tests_dir = module_dir / "tests"
    if tests_dir.exists():
        for py_file in tests_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            for line_num, model_name, ref_type in extract_model_references(py_file):
                if model_name in models_defined:
                    continue
                if model_name not in model_map:
                    continue

                required_module = model_map[model_name]
                if required_module == module_name:
                    continue

                if required_module not in declared_deps:
                    would_be_circular = check_circular_dependency(dep_graph, module_name, required_module)

                    issues.append(
                        {
                            "module": module_name,
                            "file": str(py_file.relative_to(module_dir.parent)),
                            "line": line_num,
                            "model": model_name,
                            "ref_type": ref_type,
                            "required_module": required_module,
                            "circular": would_be_circular,
                            "in_tests": True,
                        }
                    )

    return issues


def main():
    root_dir = Path(".")

    print("=" * 80)
    print("CROSS-MODULE DEPENDENCY AUDIT")
    print("=" * 80)
    print()

    # Build maps
    print("Building model → module map...")
    model_map = build_model_to_module_map(root_dir)
    print(f"  Found {len(model_map)} models across plasticos_* modules")

    print("Building dependency graph...")
    dep_graph = build_dependency_graph(root_dir)
    print(f"  Found {len(dep_graph)} plasticos_* modules")
    print()

    # Audit all modules
    all_issues = []
    circular_issues = []
    test_only_issues = []

    for module_dir in sorted(root_dir.iterdir()):
        if not module_dir.is_dir() or not module_dir.name.startswith("plasticos_"):
            continue

        issues = audit_module(module_dir, model_map, dep_graph)
        for issue in issues:
            if issue.get("circular"):
                circular_issues.append(issue)
            elif issue.get("in_tests"):
                test_only_issues.append(issue)
            else:
                all_issues.append(issue)

    # Report results
    print("=" * 80)
    print("MISSING DEPENDENCIES (can be fixed by adding to manifest)")
    print("=" * 80)

    if all_issues:
        # Group by module
        by_module = defaultdict(list)
        for issue in all_issues:
            by_module[issue["module"]].append(issue)

        for module, issues in sorted(by_module.items()):
            print(f"\n📦 {module}")
            print(f"   Missing dependency: {issues[0]['required_module']}")
            for issue in issues:
                print(f"   • {issue['file']}:{issue['line']} → {issue['model']} ({issue['ref_type']})")
    else:
        print("\n✅ No missing dependencies found in models/")

    print()
    print("=" * 80)
    print("⚠️  CIRCULAR DEPENDENCY RISKS (require architectural fix)")
    print("=" * 80)

    if circular_issues:
        by_module = defaultdict(list)
        for issue in circular_issues:
            by_module[issue["module"]].append(issue)

        for module, issues in sorted(by_module.items()):
            print(f"\n🔄 {module} → {issues[0]['required_module']} (CIRCULAR!)")
            print(f"   {issues[0]['required_module']} already depends on {module}")
            print("   Fix: Interface in base module, implementation in dependent")
            for issue in issues:
                print(f"   • {issue['file']}:{issue['line']} → {issue['model']} ({issue['ref_type']})")
    else:
        print("\n✅ No circular dependency risks found")

    print()
    print("=" * 80)
    print("📋 TEST-ONLY DEPENDENCIES (tests reference models not in manifest)")
    print("=" * 80)

    if test_only_issues:
        by_module = defaultdict(list)
        for issue in test_only_issues:
            by_module[issue["module"]].append(issue)

        for module, issues in sorted(by_module.items()):
            print(f"\n🧪 {module}")
            required_modules = set(i["required_module"] for i in issues)
            for req in sorted(required_modules):
                print(f"   Missing dependency: {req}")
            for issue in issues:
                print(f"   • {issue['file']}:{issue['line']} → {issue['model']} ({issue['ref_type']})")
    else:
        print("\n✅ No test-only dependency issues found")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Missing dependencies (fixable):     {len(all_issues)}")
    print(f"  Circular dependency risks:          {len(circular_issues)}")
    print(f"  Test-only issues:                   {len(test_only_issues)}")
    print(f"  Total issues:                       {len(all_issues) + len(circular_issues) + len(test_only_issues)}")

    if circular_issues:
        print()
        print("⚠️  CIRCULAR DEPENDENCIES require the same fix pattern as plasticos_commission:")
        print("    1. Base module defines interface (returns default/raises NotImplementedError)")
        print("    2. Dependent module inherits and provides implementation")
        print("    3. Tests for implementation go in dependent module")

    return 1 if (all_issues or circular_issues or test_only_issues) else 0


if __name__ == "__main__":
    sys.exit(main())

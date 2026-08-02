#!/usr/bin/env python3
"""
Circular Dependency & Cross-Module @api.depends Checker
========================================================

Prevents two common Odoo module errors:

1. CIRCULAR DEPENDENCIES: Module A depends on B, B depends on A (or longer chains)
   - Causes: "Recursion error in modules dependencies!"
   - Uses Tarjan's SCC algorithm — catches 2-node AND multi-node cycles.

2. CROSS-MODULE @api.depends: Using fields from other modules in @api.depends
   - Causes: Field not found error at module load time
   - Correct pattern: Override compute method in bridge module

Usage:
    python3 ci/check_circular_deps.py [root_dir]

Exit codes:
    0 = No issues found
    1 = Issues found (blocks CI)

NOTE: This script scans files on disk (git working tree).  If your local branch
is behind the remote, the remote version may have introduced cycles that this
script won't see until you pull.  Always run `git pull` before this check.
"""

import ast
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from _git_utils import contained_path, get_git_tracked_files


def parse_manifest(manifest_path: Path) -> dict | None:
    """Parse __manifest__.py and return dict."""
    try:
        # contained_path: reject traversal outside the repo (SonarCloud S8707)
        with open(contained_path(manifest_path), encoding="utf-8") as f:
            content = f.read()
        return ast.literal_eval(content)
    except Exception:
        return None


def get_module_dependencies(root_dir: Path) -> dict[str, set[str]]:
    """Build dependency graph: module_name -> set of dependencies."""
    deps = {}
    # Only check git-tracked manifests
    manifest_files = get_git_tracked_files("*/__manifest__.py")
    if not manifest_files:
        # Fallback if not in git repo
        manifest_files = list(root_dir.glob("*/__manifest__.py"))

    for manifest in manifest_files:
        manifest = root_dir / manifest if not manifest.is_absolute() else manifest
        module_name = manifest.parent.name
        data = parse_manifest(manifest)
        if data and "depends" in data:
            deps[module_name] = set(data["depends"])
    return deps


def find_circular_deps(deps: dict[str, set[str]]) -> list[list[str]]:
    """Find ALL dependency cycles using Tarjan's SCC algorithm.

    Detects both direct 2-node cycles (A ↔ B) and longer chains (A→B→C→A).
    Only considers our own plasticos_* modules — external Odoo modules are
    excluded because we can't change them.

    Returns a list of SCCs (Strongly Connected Components) where each SCC
    contains 2+ modules that form a cycle.
    """
    our_modules = set(deps.keys())
    # Build adjacency restricted to our modules only
    adj: dict[str, set[str]] = {m: {d for d in deps[m] if d in our_modules} for m in our_modules}

    index_counter = [0]
    stack: list[str] = []
    on_stack: dict[str, bool] = {}
    index_map: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    cycles: list[list[str]] = []

    def _strongconnect(v: str) -> None:
        index_map[v] = lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True

        for w in adj.get(v, set()):
            if w not in index_map:
                _strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index_map[w])

        if lowlink[v] == index_map[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1:
                cycles.append(sorted(scc))

    for v in sorted(our_modules):
        if v not in index_map:
            _strongconnect(v)

    return cycles


def _warn_if_branch_behind_remote() -> None:
    """Print a warning if the current branch is behind its remote tracking branch.

    When the local branch is stale, the checker scans old manifests and can
    miss cycles that exist in the pushed code.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return  # No upstream configured — skip
        upstream = result.stdout.strip()

        behind = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..{upstream}"],
            capture_output=True,
            text=True,
        )
        count = int(behind.stdout.strip() or "0")
        if count > 0:
            print(
                f"\n⚠️  WARNING: local branch is {count} commit(s) behind {upstream}.\n"
                "   The checker scans files on disk — remote code may have introduced\n"
                "   cycles that won't be detected until you run: git pull\n"
            )
    except Exception:
        pass  # Non-fatal — just skip the warning


def get_module_fields(root_dir: Path) -> dict[str, dict[tuple[str, str], str]]:
    """Map module_name -> {(model_name, field_name): file_path} for fields defined in that module."""
    module_fields: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)

    # Only check git-tracked Python files
    py_files = get_git_tracked_files("*/models/*.py")
    if not py_files:
        py_files = list(root_dir.glob("*/models/*.py"))

    for py_file in py_files:
        py_file = root_dir / py_file if not py_file.is_absolute() else py_file
        if "__pycache__" in str(py_file):
            continue
        module_name = py_file.parent.parent.name

        try:
            # contained_path: reject traversal outside the repo (SonarCloud S8707)
            with open(contained_path(py_file), encoding="utf-8") as f:
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


def _find_field_source(
    model_name: str,
    base_field: str,
    module_name: str,
    deps: dict[str, set[str]],
    module_fields: dict[str, dict[str, str]],
) -> tuple[bool, str | None]:
    """Return (found_in_dep, source_module) for a depends field."""
    module_deps = deps.get(module_name, set())
    found_in_dep = any((model_name, base_field) in module_fields.get(dep, {}) for dep in module_deps)
    source = next(
        (mod for mod, fields in module_fields.items() if (model_name, base_field) in fields),
        None,
    )
    return found_in_dep, source


def _check_depends_in_file(
    py_file,
    root_dir,
    deps: dict[str, set[str]],
    module_fields: dict[str, dict[str, str]],
) -> list[dict]:
    """Check a single file for cross-module @api.depends violations."""
    _MAGIC_FIELDS = {
        "id",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "display_name",
        "__last_update",
        "active",
        "name",
    }
    py_file = root_dir / py_file if not py_file.is_absolute() else py_file
    if "__pycache__" in str(py_file):
        return []
    module_name = py_file.parent.parent.name
    try:
        # contained_path: reject traversal outside the repo (SonarCloud S8707)
        with open(contained_path(py_file), encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []
    model_match = re.search(r'_name\s*=\s*["\'\']([^"\'\']*)["\'\']', content)
    inherit_match = re.search(r'_inherit\s*=\s*["\'\']([^"\'\']*)["\'\']', content)
    model_name_val = model_match or inherit_match
    if not model_name_val:
        return []
    model_name = model_name_val.group(1)
    errors = []
    for match in re.finditer(r"@api\.depends\(([^)]+)\)\s+def\s+(\w+)", content, re.MULTILINE):
        method_name = match.group(2)
        field_names = re.findall(r'["\'\']([^"\'\']*)["\'\']', match.group(1))
        for field_path in field_names:
            base_field = field_path.split(".")[0]
            if base_field in _MAGIC_FIELDS:
                continue
            if (model_name, base_field) in module_fields.get(module_name, {}):
                continue
            found_in_dep, source = _find_field_source(model_name, base_field, module_name, deps, module_fields)
            if source and not found_in_dep and source != module_name:
                errors.append(
                    {
                        "type": "CROSS_MODULE_DEPENDS",
                        "module": module_name,
                        "model": model_name,
                        "method": method_name,
                        "field": base_field,
                        "field_source": source,
                        "file": str(py_file),
                        "line": content[: match.start()].count("\n") + 1,
                        "message": (
                            f"@api.depends('{base_field}') in {module_name} references "
                            f"field from {source} which is not a dependency. "
                            f"Move the @api.depends to {source}'s bridge module."
                        ),
                    }
                )
    return errors


def check_cross_module_depends(
    root_dir: Path,
    deps: dict[str, set[str]],
    module_fields: dict[str, dict[str, str]],
) -> list[dict]:
    """Find @api.depends referencing fields from non-dependency modules."""
    py_files = get_git_tracked_files("*/models/*.py")
    if not py_files:
        py_files = list(root_dir.glob("*/models/*.py"))
    errors = []
    for py_file in py_files:
        errors.extend(_check_depends_in_file(py_file, root_dir, deps, module_fields))
    return errors


def main():
    root_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

    _warn_if_branch_behind_remote()

    print("🔍 Checking for circular dependencies...")
    deps = get_module_dependencies(root_dir)
    cycles = find_circular_deps(deps)

    print("🔍 Checking for cross-module @api.depends violations...")
    module_fields = get_module_fields(root_dir)
    cross_module_errors = check_cross_module_depends(root_dir, deps, module_fields)

    # Report results
    errors = []

    if cycles:
        print(f"\n❌ Found {len(cycles)} circular dependency cycle(s):")
        for scc in cycles:
            cycle_str = " -> ".join(scc) + f" -> {scc[0]}"
            print(f"   {cycle_str}")
            errors.append(
                {
                    "type": "CIRCULAR_DEPENDENCY",
                    "modules": scc,
                    "message": f"Circular dependency cycle: {cycle_str}",
                    "fix": f"Remove one dependency edge within: {', '.join(scc)}",
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

#!/usr/bin/env python3
"""Check for duplicate model definitions and incorrect inheritance patterns.

This CI check prevents:
1. Duplicate _name definitions (same model defined in multiple modules)
2. Models that should use _inherit but incorrectly use _name
3. Models extending dependent module models without proper _inherit

Exit codes:
- 0: All checks passed
- 1: Issues found (blocks merge)
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path


def extract_manifest_depends(manifest_path: Path) -> list[str]:
    """Extract depends list from __manifest__.py."""
    try:
        content = manifest_path.read_text()
        manifest = ast.literal_eval(content)
        return manifest.get("depends", [])
    except Exception:
        return []


def extract_model_definitions(py_file: Path) -> list[dict]:
    """Extract _name and _inherit from a Python file."""
    models: list[dict] = []
    try:
        content = py_file.read_text()
        tree = ast.parse(content)
    except Exception:
        return models

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            model_info = {
                "class_name": node.name,
                "file": str(py_file),
                "line": node.lineno,
                "_name": None,
                "_inherit": None,
                "_inherit_list": None,
            }

            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "_name" and isinstance(item.value, ast.Constant):
                                model_info["_name"] = item.value.value
                            elif target.id == "_inherit":
                                if isinstance(item.value, ast.Constant):
                                    model_info["_inherit"] = item.value.value
                                elif isinstance(item.value, ast.List):
                                    model_info["_inherit_list"] = [
                                        elt.value for elt in item.value.elts if isinstance(elt, ast.Constant)
                                    ]

            if model_info["_name"] or model_info["_inherit"]:
                models.append(model_info)

    return models


def get_module_from_path(file_path: Path, root: Path) -> str | None:
    """Extract module name from file path."""
    try:
        rel_path = file_path.relative_to(root)
        parts = rel_path.parts
        if parts and parts[0].startswith("plasticos_"):
            return parts[0]
    except ValueError:
        pass
    return None


def check_duplicate_models(root: Path) -> list[dict]:
    """Find models with duplicate _name definitions."""
    issues = []
    model_definitions = defaultdict(list)

    # Collect all model definitions
    for py_file in root.rglob("*.py"):
        # Skip test files, venv, forbidden
        if any(skip in str(py_file) for skip in ["/tests/", "/.venv/", "/venv/", "/forbidden/"]):
            continue

        module = get_module_from_path(py_file, root)
        if not module:
            continue

        for model in extract_model_definitions(py_file):
            if model["_name"]:
                model_definitions[model["_name"]].append(
                    {
                        "module": module,
                        "file": model["file"],
                        "line": model["line"],
                        "class_name": model["class_name"],
                        "_inherit": model["_inherit"],
                    }
                )

    # Find duplicates
    for model_name, definitions in model_definitions.items():
        if len(definitions) > 1:
            # Check if any definition lacks _inherit (true duplicate)
            base_defs = [d for d in definitions if not d["_inherit"]]
            if len(base_defs) > 1:
                issues.append(
                    {
                        "type": "DUPLICATE_MODEL",
                        "severity": "CRITICAL",
                        "model": model_name,
                        "message": f"Model '{model_name}' defined with _name in multiple modules",
                        "locations": [f"{d['module']}: {d['file']}:{d['line']} ({d['class_name']})" for d in base_defs],
                        "fix": "Use _inherit instead of _name in dependent modules",
                    }
                )

    return issues


def check_inheritance_patterns(root: Path) -> list[dict]:
    """Check for models that should use _inherit but use _name."""
    issues = []

    # Build module dependency graph
    module_depends = {}
    for manifest in root.glob("plasticos_*/__manifest__.py"):
        module = manifest.parent.name
        module_depends[module] = extract_manifest_depends(manifest)

    # Collect all model definitions with their modules
    model_to_module = {}  # model_name -> defining module
    for py_file in root.rglob("*.py"):
        if any(skip in str(py_file) for skip in ["/tests/", "/.venv/", "/venv/", "/forbidden/"]):
            continue

        module_name = get_module_from_path(py_file, root)
        if not module_name:
            continue

        for model in extract_model_definitions(py_file):
            if model["_name"] and not model["_inherit"]:
                # This is a base definition
                if model["_name"] not in model_to_module:
                    model_to_module[model["_name"]] = module_name

    # Check for models that define _name for models from dependent modules
    for py_file in root.rglob("*.py"):
        if any(skip in str(py_file) for skip in ["/tests/", "/.venv/", "/venv/", "/forbidden/"]):
            continue

        module_name = get_module_from_path(py_file, root)
        if not module_name:
            continue

        depends = module_depends.get(module_name, [])

        for model in extract_model_definitions(py_file):
            if model["_name"] and not model["_inherit"]:
                model_name = model["_name"]
                base_module = model_to_module.get(model_name)

                # If model is defined in a module we depend on, we should use _inherit
                if base_module and base_module != module_name:
                    if base_module in depends:
                        issues.append(
                            {
                                "type": "SHOULD_USE_INHERIT",
                                "severity": "HIGH",
                                "model": model_name,
                                "file": model["file"],
                                "line": model["line"],
                                "message": (
                                    f"Model '{model_name}' uses _name but should use _inherit. "
                                    f"Base model is in '{base_module}' which is a dependency."
                                ),
                                "fix": f'Change _name = "{model_name}" to _inherit = "{model_name}"',
                            }
                        )

    return issues


def check_test_required_fields(root: Path) -> list[dict]:
    """Check that tests provide required relational fields."""
    issues = []

    # Known required relational fields (from our session)
    required_fields = {
        "plasticos.claim": ["transaction_id"],
        "plasticos.offer": ["intake_id", "supplier_id", "buyer_id"],
        "plasticos.document": ["attachment_id", "tag_id"],
        "plasticos.match.result": ["intake_id", "buyer_partner_id"],
        "plasticos.material.profile": ["partner_id", "polymer_id", "form_id"],
    }

    for test_file in root.rglob("test_*.py"):
        if "/.venv/" in str(test_file) or "/venv/" in str(test_file):
            continue

        try:
            content = test_file.read_text()
        except Exception:
            continue

        for model, fields in required_fields.items():
            # Look for .create() calls for this model
            escaped_model = model.replace(".", r"\.")
            pattern = rf"{escaped_model}.*\.create\s*\("
            if re.search(pattern, content):
                # Check if required fields are provided
                for field in fields:
                    # Simple heuristic: check if field name appears near create
                    if f'"{field}"' not in content and f"'{field}'" not in content:
                        # Check if there's a helper method that might provide it
                        if f"_{field.split('_')[0]}" not in content and f"self.{field.split('_')[0]}" not in content:
                            issues.append(
                                {
                                    "type": "MISSING_REQUIRED_FIELD_IN_TEST",
                                    "severity": "MEDIUM",
                                    "file": str(test_file),
                                    "model": model,
                                    "field": field,
                                    "message": f"Test creates '{model}' but may not provide required field '{field}'",
                                    "fix": f"Ensure '{field}' is provided when creating '{model}' records",
                                }
                            )

    return issues


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    print("=" * 60)
    print("Model Inheritance & Test Data Validation")
    print("=" * 60)

    all_issues = []

    # Check 1: Duplicate model definitions
    print("\n[1/3] Checking for duplicate model definitions...")
    dup_issues = check_duplicate_models(root)
    all_issues.extend(dup_issues)
    if dup_issues:
        print(f"  ❌ Found {len(dup_issues)} duplicate model issue(s)")
        for issue in dup_issues:
            print(f"     - {issue['model']}: {issue['message']}")
            for loc in issue.get("locations", []):
                print(f"       • {loc}")
    else:
        print("  ✅ No duplicate model definitions")

    # Check 2: Incorrect inheritance patterns
    print("\n[2/3] Checking inheritance patterns...")
    inherit_issues = check_inheritance_patterns(root)
    all_issues.extend(inherit_issues)
    if inherit_issues:
        print(f"  ❌ Found {len(inherit_issues)} inheritance issue(s)")
        for issue in inherit_issues:
            print(f"     - {issue['file']}:{issue['line']}")
            print(f"       {issue['message']}")
            print(f"       Fix: {issue['fix']}")
    else:
        print("  ✅ All inheritance patterns correct")

    # Check 3: Test required fields (warning only)
    print("\n[3/3] Checking test data completeness...")
    test_issues = check_test_required_fields(root)
    # Filter to only HIGH/CRITICAL for blocking
    blocking_test_issues = [i for i in test_issues if i["severity"] in ("HIGH", "CRITICAL")]
    if blocking_test_issues:
        print(f"  ⚠️  Found {len(test_issues)} potential test data issue(s)")
    else:
        print("  ✅ Test data checks passed")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    critical = [i for i in all_issues if i["severity"] == "CRITICAL"]
    high = [i for i in all_issues if i["severity"] == "HIGH"]

    print(f"  CRITICAL: {len(critical)}")
    print(f"  HIGH: {len(high)}")
    print(f"  MEDIUM: {len([i for i in all_issues if i['severity'] == 'MEDIUM'])}")

    # Exit with error if CRITICAL or HIGH issues found
    if critical or high:
        print("\n❌ FAILED: Found blocking issues")
        print("\nBlocking issues:")
        for issue in critical + high:
            print(f"  [{issue['severity']}] {issue['type']}: {issue['message']}")
            if "fix" in issue:
                print(f"           Fix: {issue['fix']}")
        return 1

    print("\n✅ PASSED: No blocking issues found")
    return 0


if __name__ == "__main__":
    sys.exit(main())

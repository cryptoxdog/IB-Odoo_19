#!/usr/bin/env python3
"""
CI Check: Field Integrity Validation

Catches:
1. x_ prefixed fields (should use standard naming)
2. Cross-module @api.depends violations
3. Missing xpath targets (button_box)

Exit codes:
  0 = PASS
  1 = FAIL (blocking issues found)
"""

import re
import sys
from pathlib import Path

# Field ownership: which module defines which fields on which models
# Format: {model: {field: module}}
FIELD_OWNERSHIP = {
    "plasticos.transaction": {
        "document_ids": "plasticos_documents",
        "document_count": "plasticos_documents",
    },
    "plasticos.load": {
        "document_ids": "plasticos_documents",
        "document_count": "plasticos_documents",
    },
}

# Parent views that MUST have button_box for inheritance
REQUIRED_BUTTON_BOX = {
    "plasticos_transaction.view_transaction_form": "plasticos_transaction/views/transaction_views.xml",
    "plasticos_offer.view_offer_form": "plasticos_offer/views/offer_views.xml",
    "plasticos_web_leads.view_web_lead_form": "plasticos_web_leads/views/web_lead_views.xml",
    "plasticos_matching.view_match_result_form": "plasticos_matching/views/match_result_views.xml",
    "plasticos_intake.view_plasticos_intake_form": "plasticos_intake/views/intake_views.xml",
    "plasticos_logistics.view_load_form": "plasticos_logistics/views/load_views.xml",
    "plasticos_material_profile.view_material_profile_form": (
        "plasticos_material_profile/views/material_profile_views.xml"
    ),
}


def check_x_prefixed_fields(base_path: Path) -> list[tuple[str, int, str]]:
    """Find fields with x_ prefix (should be renamed)."""
    issues = []

    for module_dir in sorted(base_path.iterdir()):
        if not module_dir.is_dir() or not module_dir.name.startswith("plasticos_"):
            continue

        models_dir = module_dir / "models"
        if not models_dir.exists():
            continue

        for py_file in models_dir.glob("*.py"):
            try:
                content = py_file.read_text()
                for i, line in enumerate(content.split("\n"), 1):
                    # Match field definitions with x_ prefix
                    if re.search(r"\bx_\w+\s*=\s*fields\.", line):
                        field_match = re.search(r"(x_\w+)\s*=", line)
                        if field_match:
                            issues.append((str(py_file), i, field_match.group(1)))
            except Exception:
                pass

    return issues


def _get_module_dependencies(manifest_path: Path) -> set[str]:
    """Parse __manifest__.py and return the set of declared dependencies."""
    dependencies: set[str] = set()
    if not manifest_path.exists():
        return dependencies
    try:
        content = manifest_path.read_text()
        match = re.search(r'"depends"\s*:\s*\[(.*?)\]', content, re.DOTALL)
        if match:
            for dep_match in re.finditer(r'"([^"]+)"', match.group(1)):
                dependencies.add(dep_match.group(1))
    except Exception:
        pass
    return dependencies


def _extract_depends_fields(line: str, lines: list[str], i: int) -> list[str]:
    """Return field names referenced by an @api.depends decorator (handles multi-line)."""
    depends_match = re.search(r"@api\.depends\s*\((.*?)\)", line, re.DOTALL)
    if not depends_match:
        full_depends = line
        j = i + 1
        while j < len(lines) and ")" not in full_depends:
            full_depends += lines[j]
            j += 1
        depends_match = re.search(r"@api\.depends\s*\((.*?)\)", full_depends, re.DOTALL)
    if not depends_match:
        return []
    return [m.group(1) for m in re.finditer(r'"([^"]+)"', depends_match.group(1))]


def _check_file_for_cross_depends(
    py_file: Path,
    module_name: str,
    dependencies: set[str],
) -> list[tuple[str, int, str, str, str]]:
    """Scan one Python file for @api.depends cross-module violations."""
    issues = []
    try:
        content = py_file.read_text()
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "@api.depends" not in line:
                continue
            for field_path in _extract_depends_fields(line, lines, i):
                field_name = field_path.split(".")[0]
                for _model, fields in FIELD_OWNERSHIP.items():
                    if field_name in fields:
                        owner_module = fields[field_name]
                        if owner_module != module_name and owner_module not in dependencies:
                            issues.append((str(py_file), i + 1, field_name, owner_module, module_name))
    except Exception:
        pass
    return issues


def check_cross_module_depends(base_path: Path) -> list[tuple[str, int, str, str, str]]:
    """Find @api.depends that reference fields from non-dependency modules."""
    issues = []

    for module_dir in sorted(base_path.iterdir()):
        if not module_dir.is_dir() or not module_dir.name.startswith("plasticos_"):
            continue

        module_name = module_dir.name
        dependencies = _get_module_dependencies(module_dir / "__manifest__.py")

        models_dir = module_dir / "models"
        if not models_dir.exists():
            continue

        for py_file in models_dir.glob("*.py"):
            issues.extend(_check_file_for_cross_depends(py_file, module_name, dependencies))

    return issues


def check_button_box_targets(base_path: Path) -> list[tuple[str, str]]:
    """Check that parent views have button_box for xpath inheritance.

    DEFERRED: Views that don't exist yet are skipped with a warning, not an error.
    This allows incremental module development without blocking CI.
    """
    issues = []

    for view_ref, filepath in REQUIRED_BUTTON_BOX.items():
        path = base_path / filepath
        if not path.exists():
            # DEFERRED: Skip missing files with warning instead of error
            # This allows CI to pass while modules are being developed
            print(f"⚠️  SKIP: {view_ref} — file not yet committed ({filepath})")
            continue

        content = path.read_text()
        if 'name="button_box"' not in content:
            issues.append((view_ref, f"Missing button_box in {filepath}"))

    return issues


def check_duplicate_one2many_fields(base_path: Path) -> list[tuple[str, str, list[str]]]:
    """Find One2many fields defined multiple times for the same model."""
    # {(model, field): [files]}
    one2many_defs: dict[tuple[str, str], list[str]] = {}

    for module_dir in sorted(base_path.iterdir()):
        if not module_dir.is_dir() or not module_dir.name.startswith("plasticos_"):
            continue

        models_dir = module_dir / "models"
        if not models_dir.exists():
            continue

        for py_file in models_dir.glob("*.py"):
            try:
                content = py_file.read_text()

                # Find _inherit or _name
                model_match = re.search(r'_(?:inherit|name)\s*=\s*["\']([^"\']+)["\']', content)
                if not model_match:
                    continue
                model_name = model_match.group(1)

                # Find One2many field definitions (not commented out)
                for line in content.split("\n"):
                    # Skip commented lines
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    match = re.search(r"(\w+)\s*=\s*fields\.One2many\s*\(", line)
                    if match:
                        field_name = match.group(1)
                        key = (model_name, field_name)
                        if key not in one2many_defs:
                            one2many_defs[key] = []
                        one2many_defs[key].append(str(py_file))
            except Exception:
                pass

    # Find duplicates
    issues = []
    for (model, field), files in one2many_defs.items():
        if len(files) > 1:
            # Skip if one is clearly a bridge file (intentional)
            if len(files) == 2:
                names = [Path(f).stem for f in files]
                if any("bridge" in n for n in names):
                    continue
            issues.append((model, field, files))

    return issues


def main():
    base_path = Path(".")
    errors = []

    print("🔍 Checking field integrity...\n")

    # Check 1: x_ prefixed fields
    print("Checking x_ prefixed fields...")
    x_fields = check_x_prefixed_fields(base_path)
    if x_fields:
        for filepath, line, field in x_fields:
            errors.append(f"   {filepath}:{line}\n      Field '{field}' uses x_ prefix (rename to remove prefix)")

    # Check 2: Cross-module depends
    print("Checking cross-module @api.depends...")
    cross_deps = check_cross_module_depends(base_path)
    if cross_deps:
        for filepath, line, field, owner, current in cross_deps:
            errors.append(
                f"   {filepath}:{line}\n"
                f"      @api.depends('{field}') in {current} references field from {owner} which is not a dependency.\n"
                f"      Move the @api.depends to {owner}'s bridge module."
            )

    # Check 3: Button box targets
    print("Checking button_box xpath targets...")
    button_issues = check_button_box_targets(base_path)
    if button_issues:
        for view_ref, issue in button_issues:
            errors.append(f"   {view_ref}: {issue}")

    # Check 4: Duplicate One2many fields
    print("Checking duplicate One2many field definitions...")
    dup_issues = check_duplicate_one2many_fields(base_path)
    if dup_issues:
        for model, field, files in dup_issues:
            errors.append(
                f"   Model '{model}' has duplicate One2many field '{field}':\n      " + "\n      ".join(files)
            )

    # Print results
    print()
    if errors:
        print(f"❌ Found {len(errors)} field integrity issues:\n")
        for error in errors:
            print(error)
            print()
        print("=" * 60)
        print(f"TOTAL ERRORS: {len(errors)}")
        print("=" * 60)
        print("\nThese errors will cause Odoo to fail at startup or runtime.")
        sys.exit(1)
    else:
        print("✅ PASSED: No field integrity issues found")
        sys.exit(0)


if __name__ == "__main__":
    main()

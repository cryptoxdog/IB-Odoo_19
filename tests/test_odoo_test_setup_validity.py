"""
Static analysis of Odoo test files to catch common setup issues.

This test runs WITHOUT Odoo runtime and catches issues that would otherwise
only surface during module installation on staging/production.

Checks:
1. Test partners that should be facilities have parent_id set
2. Test data uses correct field names (not deprecated x_ prefixes)
3. Required fields are present in test create() calls
"""

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class SetupViolation(NamedTuple):
    file: Path
    line: int
    issue: str
    suggestion: str

    def format(self) -> str:
        return f"{self.file.relative_to(ROOT)}:{self.line}: {self.issue}\n  → {self.suggestion}"


def find_odoo_test_files() -> list[Path]:
    """Find all Odoo test files (in module tests/ folders)."""
    test_files = []
    for module_dir in ROOT.iterdir():
        if module_dir.is_dir() and module_dir.name.startswith("plasticos_"):
            tests_dir = module_dir / "tests"
            if tests_dir.exists():
                for f in tests_dir.glob("test_*.py"):
                    test_files.append(f)
    return test_files


def check_facility_partner_setup(file: Path, tree: ast.AST) -> list[SetupViolation]:
    """
    Check that test partners used with material profiles have parent_id.

    The _check_partner_is_facility constraint requires partner_id.parent_id to exist.

    This check looks for material.profile.create() calls and traces back to see
    if the partner variable was created without parent_id.
    """
    violations = []
    file_content = file.read_text()

    # Only check files that actually CREATE material profiles
    if 'plasticos.material.profile"].create' not in file_content:
        return violations

    # Find material profile creates and extract partner variable names
    # Pattern: plasticos.material.profile"].create({..."partner_id": self.X.id or cls.X.id
    # But skip if inside assertRaises (testing validation)

    # First, find lines that are inside assertRaises blocks
    assertraises_ranges = []
    for match in re.finditer(r"with self\.assertRaises\([^)]+\):", file_content):
        start = file_content[: match.end()].count("\n") + 1
        # Find the end of the with block (next line with same or less indentation)
        indent = len(match.group(0)) - len(match.group(0).lstrip())
        remaining = file_content[match.end() :]
        end = start
        for line in remaining.split("\n")[1:]:  # Skip the with line itself
            if line.strip() and not line.startswith(" " * (indent + 1)):
                break
            end += 1
        assertraises_ranges.append((start, end))

    def is_in_assertraises(line_num):
        for start, end in assertraises_ranges:
            if start <= line_num <= end:
                return True
        return False

    # Find material profile creates with partner_id
    profile_pattern = re.compile(
        r'plasticos\.material\.profile"\]\.create\s*\(\s*\{[^}]*"partner_id":\s*(self|cls)\.(\w+)\.id', re.DOTALL
    )

    partner_vars_in_profiles = set()
    for match in profile_pattern.finditer(file_content):
        line_num = file_content[: match.start()].count("\n") + 1
        if not is_in_assertraises(line_num):
            partner_vars_in_profiles.add(match.group(2))

    # Now check if those partner variables were created without parent_id
    # Pattern: cls.X = env["res.partner"].create({...}) without parent_id
    partner_create_pattern = re.compile(
        r'(cls|self)\.(\w+)\s*=\s*(?:cls|self)\.env\["res\.partner"\]\.create\s*\(\s*\{([^}]*)\}', re.DOTALL
    )

    for match in partner_create_pattern.finditer(file_content):
        var_name = match.group(2)
        create_dict = match.group(3)

        if var_name in partner_vars_in_profiles:
            if '"parent_id"' not in create_dict and "'parent_id'" not in create_dict:
                line_num = file_content[: match.start()].count("\n") + 1
                violations.append(
                    SetupViolation(
                        file=file,
                        line=line_num,
                        issue=f"Partner '{var_name}' used in material.profile.create() but missing parent_id",
                        suggestion="Add parent_id (required by _check_partner_is_facility)",
                    )
                )

    return violations


def check_deprecated_field_names(file: Path, tree: ast.AST) -> list[SetupViolation]:
    """Check for deprecated x_ prefixed field names in test data."""
    violations = []
    source = file.read_text()

    # Known deprecated fields (x_ prefix removed in Odoo 19 migration)
    deprecated_fields = {
        "x_facility_role": "facility_role",
        "x_ready_for_pickup": "ready_for_pickup",
        "x_ready_confirmed_on": "ready_confirmed_on",
        "x_buyer_id": "buyer_id",
        "x_followup_count": "followup_count",
        "x_last_followup_on": "last_followup_on",
        "x_delivery_term": "delivery_term",
        "x_appt_requested": "appt_requested",
        "x_appt_requested_on": "appt_requested_on",
        "x_trucker_id": "trucker_id",
        "x_receipt_confirmation": "receipt_confirmation",
        "x_trucker_notified_on": "trucker_notified_on",
        "x_trucker_followup_count": "trucker_followup_count",
        "groups_id": "group_ids",
    }

    for old_name, new_name in deprecated_fields.items():
        for match in re.finditer(rf'["\']({re.escape(old_name)})["\']', source):
            line_num = source[: match.start()].count("\n") + 1
            violations.append(
                SetupViolation(
                    file=file,
                    line=line_num,
                    issue=f"Deprecated field name '{old_name}' used",
                    suggestion=f"Use '{new_name}' instead (renamed in Odoo 19 migration)",
                )
            )

    return violations


def check_required_fields_in_create(file: Path, tree: ast.AST) -> list[SetupViolation]:
    """Check that required fields are present in create() calls."""
    violations = []

    # Model -> required fields mapping
    required_fields = {
        "plasticos.material.profile": ["partner_id", "polymer_id"],
        "plasticos.facility.profile": ["partner_id"],
        "plasticos.claim": ["transaction_id"],
    }

    # Find all create() calls that are inside assertRaises blocks (testing validation)
    # These are intentionally missing fields to test constraints
    assertraises_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                if (
                    isinstance(item.context_expr, ast.Call)
                    and isinstance(item.context_expr.func, ast.Attribute)
                    and item.context_expr.func.attr == "assertRaises"
                ):
                    # Mark all lines in this with block as "testing validation"
                    for child in ast.walk(node):
                        if hasattr(child, "lineno"):
                            assertraises_lines.add(child.lineno)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Skip if inside assertRaises block (testing validation)
            if node.lineno in assertraises_lines:
                continue

            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "create"
                and isinstance(node.func.value, ast.Subscript)
            ):
                subscript = node.func.value
                if isinstance(subscript.slice, ast.Constant):
                    model_name = subscript.slice.value
                    if model_name in required_fields:
                        if node.args and isinstance(node.args[0], ast.Dict):
                            keys = [k.value if isinstance(k, ast.Constant) else None for k in node.args[0].keys]
                            for req_field in required_fields[model_name]:
                                if req_field not in keys:
                                    violations.append(
                                        SetupViolation(
                                            file=file,
                                            line=node.lineno,
                                            issue=f"Required field '{req_field}' missing in {model_name}.create()",
                                            suggestion=f"Add '{req_field}' to the create dict",
                                        )
                                    )
    return violations


def run_all_checks() -> list[SetupViolation]:
    """Run all static checks on Odoo test files."""
    all_violations = []

    for test_file in find_odoo_test_files():
        try:
            source = test_file.read_text()
            tree = ast.parse(source, filename=str(test_file))
        except SyntaxError:
            continue

        all_violations.extend(check_facility_partner_setup(test_file, tree))
        all_violations.extend(check_deprecated_field_names(test_file, tree))
        all_violations.extend(check_required_fields_in_create(test_file, tree))

    return all_violations


def test_odoo_test_setup_validity():
    """Main test: validate all Odoo test setups."""
    violations = run_all_checks()
    assert not violations, "Test setup issues found:\n" + "\n".join(v.format() for v in violations)


if __name__ == "__main__":
    violations = run_all_checks()
    if violations:
        print("Test setup issues found:")
        for v in violations:
            print(f"  {v.format()}")
        sys.exit(1)
    else:
        print("All test setups valid.")

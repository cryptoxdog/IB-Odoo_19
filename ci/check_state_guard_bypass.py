#!/usr/bin/env python3
"""
CI Check: State Guard Bypass Validation
========================================

Catches server action code that writes to the 'state' field on models
with _validate_state_transition without using bypass_state_guard context.

What this prevents:
    - UserError at runtime when automation fires and hits the state guard
    - Silent failures where state transitions are blocked by the guard
    - Production-blocking bugs where delivery/dispatch automations fail

Detection logic:
    1. Find all ir.actions.server records with inline Python code
    2. Look for .write({'state': ...}) calls
    3. Flag any that don't use .with_context(bypass_state_guard=True)

Exit codes:
    0 = PASS
    1 = FAIL (blocking issues found)
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from _git_utils import get_git_tracked_files

# Models known to have _validate_state_transition (auto-detected below)
GUARDED_MODELS: set[str] = set()

# Pattern: .write({'state': ...}) without .with_context(bypass_state_guard=True)
STATE_WRITE_PATTERN = re.compile(
    r"""
    \.write\s*\(\s*\{       # .write({
    [^}]*                   # anything inside the dict
    ['"]state['"]\s*:       # 'state': or "state":
    """,
    re.VERBOSE | re.DOTALL,
)

BYPASS_PATTERN = re.compile(r"\.with_context\s*\(\s*bypass_state_guard\s*=\s*True\s*\)")


def _detect_guarded_models(root_dir: Path) -> set[str]:
    """Scan Python model files for classes that define _validate_state_transition."""
    guarded = set()
    py_files = get_git_tracked_files("*/models/*.py")
    if not py_files:
        py_files = list(root_dir.glob("plasticos_*/models/*.py"))

    name_pattern = re.compile(r'_name\s*=\s*["\']([a-z][a-z0-9_.]+)["\']')
    inherit_pattern = re.compile(r'_inherit\s*=\s*["\']([a-z][a-z0-9_.]+)["\']')

    for py_file in py_files:
        py_path = root_dir / py_file if not py_file.is_absolute() else py_file
        if ".venv" in str(py_path):
            continue
        try:
            content = py_path.read_text(encoding="utf-8")
        except Exception:
            continue

        if "def _validate_state_transition" not in content:
            continue

        for m in name_pattern.finditer(content):
            guarded.add(m.group(1))
        for m in inherit_pattern.finditer(content):
            guarded.add(m.group(1))

    return guarded


def _resolve_model_from_ref(model_id_ref: str) -> str | None:
    """Convert model_id ref like 'plasticos_transaction.model_plasticos_transaction' to 'plasticos.transaction'."""
    if "." not in model_id_ref:
        return None
    _, model_part = model_id_ref.split(".", 1)
    if not model_part.startswith("model_"):
        return None
    return model_part[6:].replace("_", ".")


def _find_model_for_variable(code: str, var_name: str) -> str | None:
    """Try to resolve what model a variable points to from env['model.name'] patterns."""
    pattern = re.compile(rf"""{re.escape(var_name)}\s*=\s*env\[['"]([a-z][a-z0-9_.]+)['"]\]""")
    m = pattern.search(code)
    return m.group(1) if m else None


def check_state_guard_bypass(root_dir: Path, guarded_models: set[str]) -> list[dict]:
    """Check server action code for state writes missing bypass_state_guard."""
    issues = []

    xml_files = get_git_tracked_files("*/data/*.xml")
    if not xml_files:
        xml_files = list(root_dir.glob("plasticos_*/data/*.xml"))

    for xml_file in xml_files:
        xml_path = root_dir / xml_file if not xml_file.is_absolute() else xml_file
        if ".venv" in str(xml_path):
            continue

        try:
            tree = ET.parse(xml_path)  # nosec B314
        except ET.ParseError:
            continue

        root = tree.getroot()

        for rec in root.findall(".//record"):
            if rec.get("model") != "ir.actions.server":
                continue

            rec_id = rec.get("id", "")
            model_ref = ""
            code = ""

            for field in rec.findall("field"):
                if field.get("name") == "model_id":
                    model_ref = field.get("ref", "")
                elif field.get("name") == "code":
                    code = (field.text or "").strip()

            if not code:
                continue

            # Find all state writes
            for match in STATE_WRITE_PATTERN.finditer(code):
                write_pos = match.start()
                # Get the ~200 chars before the write to check for with_context
                preceding = code[max(0, write_pos - 200) : write_pos + match.end() - match.start()]

                if BYPASS_PATTERN.search(preceding):
                    continue

                # Check the full line containing the write
                line_start = code.rfind("\n", 0, write_pos) + 1
                line_end = code.find("\n", write_pos)
                if line_end == -1:
                    line_end = len(code)
                full_line = code[line_start:line_end].strip()

                if "bypass_state_guard" in full_line:
                    continue

                target_model = _resolve_model_from_ref(model_ref) if model_ref else None
                code_models = set(re.findall(r"env\[['\"]([\w.]+)['\"]\]", code))
                guarded_hit = False
                if target_model in guarded_models:
                    guarded_hit = True
                for cm in code_models:
                    if cm in guarded_models:
                        guarded_hit = True

                severity = "BLOCKER" if guarded_hit else "WARNING"

                issues.append(
                    {
                        "file": str(xml_path.relative_to(root_dir)),
                        "record_id": rec_id,
                        "model": target_model or "<unknown>",
                        "guarded": guarded_hit,
                        "line": full_line[:120],
                        "severity": severity,
                    }
                )

    return issues


def check_python_state_writes(root_dir: Path, guarded_models: set[str]) -> list[dict]:
    """Check Python model methods for state writes in automation/cron contexts.

    Only flags cron methods — the model's own action_* methods are the
    canonical way to change state and do their own validation.
    """
    issues = []

    py_files = get_git_tracked_files("*/models/*.py")
    if not py_files:
        py_files = list(root_dir.glob("plasticos_*/models/*.py"))

    for py_file in py_files:
        py_path = root_dir / py_file if not py_file.is_absolute() else py_file
        if ".venv" in str(py_path):
            continue

        try:
            content = py_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Check if this file inherits a guarded model
        inherit_match = re.search(r'_inherit\s*=\s*["\']([a-z][a-z0-9_.]+)["\']', content)
        name_match = re.search(r'_name\s*=\s*["\']([a-z][a-z0-9_.]+)["\']', content)
        match = name_match or inherit_match
        if not match:
            continue
        model_name = match.group(1)

        if model_name not in guarded_models:
            continue

        lines = content.split("\n")
        current_method = ""
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            method_match = re.match(r"\s+def (\w+)\s*\(", line)
            if method_match:
                current_method = method_match.group(1)

            # action_* methods are the model's own state transition handlers
            if current_method.startswith("action_") or current_method == "_validate_state_transition":
                continue

            if STATE_WRITE_PATTERN.search(stripped):
                context_window = "\n".join(lines[max(0, i - 5) : i])
                if "bypass_state_guard" in context_window or "bypass_state_guard" in stripped:
                    continue

                issues.append(
                    {
                        "file": str(py_path.relative_to(root_dir)),
                        "record_id": f"line:{i}:{current_method or '<module>'}",
                        "model": model_name,
                        "guarded": True,
                        "line": stripped[:120],
                        "severity": "HIGH",
                    }
                )

    return issues


def main():
    root_dir = Path(".")

    print("=" * 70)
    print("STATE GUARD BYPASS CHECK")
    print("=" * 70)
    print()

    guarded = _detect_guarded_models(root_dir)
    if guarded:
        print(f"Guarded models (have _validate_state_transition): {', '.join(sorted(guarded))}")
    else:
        print("No guarded models found — checking XML server actions only")
    print()

    xml_issues = check_state_guard_bypass(root_dir, guarded)
    py_issues = check_python_state_writes(root_dir, guarded)
    issues = xml_issues + py_issues

    if not issues:
        print("✅ PASSED: All state writes use bypass_state_guard where needed")
        sys.exit(0)

    blockers = [i for i in issues if i["severity"] == "BLOCKER"]
    highs = [i for i in issues if i["severity"] == "HIGH"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]

    print(f"❌ Found {len(issues)} state guard bypass issues")
    print(f"   BLOCKER: {len(blockers)}  |  HIGH: {len(highs)}  |  WARNING: {len(warnings)}")
    print()

    for issue in sorted(issues, key=lambda x: ("BLOCKER", "HIGH", "WARNING").index(x["severity"])):
        sev = issue["severity"]
        guarded = " [GUARDED MODEL]" if issue["guarded"] else ""
        print(f"  [{sev}]{guarded} {issue['file']} :: {issue['record_id']}")
        print(f"         Model: {issue['model']}")
        print(f"         Code:  {issue['line']}")
        print()

    print("-" * 70)
    print("HOW TO FIX:")
    print("-" * 70)
    print("""
  Change:
    record.write({'state': 'new_state'})

  To:
    record.with_context(bypass_state_guard=True).write({'state': 'new_state'})

  Models with _validate_state_transition will raise UserError if state
  is written without the bypass context. This is by design — automations
  and crons must explicitly opt in.
""")

    sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
XPath Anchor Stability Checker for Odoo 19 XML Views.

Detects risky XPath patterns that can cause silent UI corruption:
- Multi-match field selectors (field exists in both form and list)
- Unscoped list field selectors (missing //list/ prefix)
- Class-based anchors (fragile @class selectors)
- Unscoped notebook selectors (missing [1] index)
- Duplicate xpath usage in same view

Exit codes:
- 0: No issues or only LOW severity
- 1: CRITICAL or HIGH issues found (blocks CI)

Usage:
    python3 ci/check_xpath_stability.py [path]
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple

from _git_utils import get_git_tracked_files


class Finding(NamedTuple):
    file: str
    view_id: str
    xpath: str
    severity: str
    issue_type: str
    message: str
    fix_suggestion: str


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# Patterns that indicate risky xpaths
RISKY_PATTERNS = [
    # Class-based anchors without name fallback
    (
        r'//div\[@class=[\'"]oe_title[\'"]\](?!\[1\])',
        "CLASS_BASED_ANCHOR",
        "HIGH",
        "Class-based anchor without index - fragile to upstream changes",
        "Add [1] index: //div[@class='oe_title'][1]",
    ),
    # Unscoped notebook selectors
    (
        r"^//notebook(?!\[|\/)$",
        "UNSCOPED_NOTEBOOK",
        "MEDIUM",
        "Unscoped notebook selector - assumes single notebook",
        "Add index: //notebook[1]",
    ),
    # Sheet/notebook without index
    (
        r"//sheet/notebook(?!\[)",
        "UNSCOPED_SHEET_NOTEBOOK",
        "MEDIUM",
        "Sheet/notebook without index - may match wrong notebook",
        "Add index: //sheet/notebook[1]",
    ),
]

# Known safe patterns (whitelist)
SAFE_PATTERNS = [
    r"//list/field\[@name=",  # Properly scoped list field
    r"//notebook\[1\]",  # Indexed notebook
    r"//notebook//field\[@name=",  # Scoped to notebook
    r"//page\[@name=",  # Named page anchor
    r"//group\[@name=",  # Named group anchor
    r"//div\[@name=",  # Named div anchor
    r'\[@class=[\'"]oe_title[\'"]\]\[1\]',  # Indexed class selector
    r'//field\[@name=[\'"](\w+)[\'"]\]//list',  # Field containing list (one2many)
]


def is_safe_xpath(xpath: str) -> bool:
    """Check if xpath matches known safe patterns."""
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, xpath):
            return True
    return False


def check_xpath(xpath: str, file_path: str, view_id: str) -> list[Finding]:
    """Check a single xpath for risky patterns."""
    findings: list[Finding] = []

    if is_safe_xpath(xpath):
        return findings

    for pattern, issue_type, severity, message, fix_template in RISKY_PATTERNS:
        match = re.search(pattern, xpath)
        if match:
            fix = fix_template
            if "{field}" in fix and match.groups():
                fix = fix.format(field=match.group(1))

            findings.append(
                Finding(
                    file=file_path,
                    view_id=view_id,
                    xpath=xpath,
                    severity=severity,
                    issue_type=issue_type,
                    message=message,
                    fix_suggestion=fix,
                )
            )

    return findings


def is_list_view_inheritance(record: ET.Element) -> bool:
    """Check if this view inherits a list/tree view."""
    inherit_field = record.find("field[@name='inherit_id']")
    if inherit_field is None:
        return False

    ref = inherit_field.get("ref", "")
    # Common list view naming patterns
    return any(pattern in ref.lower() for pattern in ["_list", "_tree", "view_list", "view_tree"])


def analyze_xml_file(file_path: Path) -> list[Finding]:
    """Analyze a single XML file for xpath stability issues."""
    findings = []

    try:
        tree = ET.parse(file_path)  # nosec B314 — internal CI tool, trusted repo XML files
        root = tree.getroot()
    except ET.ParseError as e:
        return [
            Finding(
                file=str(file_path),
                view_id="N/A",
                xpath="N/A",
                severity="HIGH",
                issue_type="XML_PARSE_ERROR",
                message=f"Failed to parse XML: {e}",
                fix_suggestion="Fix XML syntax errors",
            )
        ]

    # Find all view records
    for record in root.findall(".//record[@model='ir.ui.view']"):
        view_id = record.get("id", "unknown")

        # Check if this is an inherited view (has inherit_id)
        inherit_field = record.find("field[@name='inherit_id']")
        if inherit_field is None:
            continue  # Skip non-inherited views

        # Find all xpath elements
        arch_field = record.find("field[@name='arch']")
        if arch_field is None:
            continue

        # Check if this inherits a list view
        is_list_inherit = is_list_view_inheritance(record)

        for xpath_elem in arch_field.findall(".//xpath"):
            expr = xpath_elem.get("expr", "")
            if not expr:
                continue

            findings.extend(check_xpath(expr, str(file_path), view_id))

            # Additional check: unscoped field in list view inheritance
            if is_list_inherit:
                field_match = re.match(r'^//field\[@name=[\'"](\w+)[\'"]\]$', expr)
                if field_match and not is_safe_xpath(expr):
                    findings.append(
                        Finding(
                            file=str(file_path),
                            view_id=view_id,
                            xpath=expr,
                            severity="MEDIUM",
                            issue_type="UNSCOPED_LIST_FIELD",
                            message="Unscoped field in list view - may match nested lists",
                            fix_suggestion=f"Use //list/field[@name='{field_match.group(1)}']",
                        )
                    )

    # Check for duplicate xpaths in same view WITH SAME POSITION
    for record in root.findall(".//record[@model='ir.ui.view']"):
        view_id = record.get("id", "unknown")
        arch_field = record.find("field[@name='arch']")
        if arch_field is None:
            continue

        # Track (expr, position) pairs
        xpath_positions: list[tuple[str, str]] = []
        for xpath_elem in arch_field.findall(".//xpath"):
            expr = xpath_elem.get("expr", "")
            position = xpath_elem.get("position", "")
            if expr:
                xpath_positions.append((expr, position))

        # Check for duplicates with SAME position (different positions are OK)
        seen: set[tuple[str, str]] = set()
        for expr, position in xpath_positions:
            key = (expr, position)
            if key in seen:
                findings.append(
                    Finding(
                        file=str(file_path),
                        view_id=view_id,
                        xpath=f"{expr} (position={position})",
                        severity="HIGH",
                        issue_type="DUPLICATE_XPATH",
                        message="Same xpath+position used multiple times - consolidate",
                        fix_suggestion="Combine content into single xpath block",
                    )
                )
            seen.add(key)

    return findings


def scan_directory(path: Path) -> list[Finding]:
    """Scan directory for XML files and analyze them."""
    all_findings = []

    # Find all git-tracked XML files in plasticos_* modules
    xml_files = get_git_tracked_files("plasticos_*/views/*.xml")
    if not xml_files:
        # Fallback if not in git repo
        xml_files = list(path.rglob("plasticos_*/views/*.xml"))

    for xml_file in xml_files:
        xml_file = path / xml_file if not xml_file.is_absolute() else xml_file
        findings = analyze_xml_file(xml_file)
        all_findings.extend(findings)

    return all_findings


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    print(f"🔍 Scanning {path} for XPath stability issues...")
    findings = scan_directory(path)

    # Sort by severity
    findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 99))

    # Count by severity
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    # Output results
    print("\n📊 XPath Stability Report")
    print(f"   CRITICAL: {counts['CRITICAL']}")
    print(f"   HIGH:     {counts['HIGH']}")
    print(f"   MEDIUM:   {counts['MEDIUM']}")
    print(f"   LOW:      {counts['LOW']}")

    if findings:
        print(f"\n{'=' * 70}")
        for f in findings:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(f.severity, "⚪")
            print(f"\n{icon} [{f.severity}] {f.issue_type}")
            print(f"   File:  {f.file}")
            print(f"   View:  {f.view_id}")
            print(f"   XPath: {f.xpath}")
            print(f"   Issue: {f.message}")
            print(f"   Fix:   {f.fix_suggestion}")

    # Write JSON report
    report = [f._asdict() for f in findings]
    with open("xpath_stability_report.json", "w") as fp:
        json.dump(report, fp, indent=2)
    print("\n📄 Report written to xpath_stability_report.json")

    # Exit with error if CRITICAL or HIGH issues found
    if counts["CRITICAL"] > 0 or counts["HIGH"] > 0:
        print(f"\n❌ FAILED: {counts['CRITICAL']} CRITICAL, {counts['HIGH']} HIGH issues")
        sys.exit(1)
    else:
        print("\n✅ PASSED: No CRITICAL or HIGH severity issues")
        sys.exit(0)


if __name__ == "__main__":
    main()

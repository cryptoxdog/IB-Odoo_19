#!/usr/bin/env python3
"""Migrate plasticos test files to use PlasticosTestCase base class.

Replaces TransactionCase (and TransactionCase + PlastOSTestFactoryMixin) with
PlasticosTestCase from plasticos_base.test_common.

Phases:
  1. migrate: Replace imports and class bases (TransactionCase -> PlasticosTestCase)
  2. cleanup: Remove redundant setUpClass lines and use default_* fixtures

Usage:
    python tools/migrate_plasticos_tests.py [--dry-run]           # migrate only
    python tools/migrate_plasticos_tests.py --cleanup [--dry-run]  # migrate + cleanup
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLASTICOS_PATTERN = "plasticos_*/tests/test_*.py"
PLASTICOS_BASE_PATTERN = "plasticos_base/tests/test_*.py"
ROOT_TESTS_PATTERN = "tests/**/test_*.py"

# Replace self.partner / cls.partner with default when removing redundant setup
REPLACE_PARTNER = re.compile(r"\b(cls|self)\.partner\b")
REPLACE_POLYMER = re.compile(r"\b(cls|self)\.polymer\b")
REPLACE_FORM = re.compile(r"\b(cls|self)\.form\b")


# Import line patterns to replace
# PlasticosTestCase comes from plasticos_base; preserve HttpCase, tagged, etc.


def _replace_odoo_tests_import(m: re.Match) -> str:
    """Replace 'from odoo.tests import TransactionCase, tagged' (or similar)."""
    orig = m.group(0)
    has_tagged = "tagged" in orig
    lines = ["from odoo.addons.plasticos_base.test_common import PlasticosTestCase"]
    if has_tagged:
        lines.append("from odoo.tests import tagged")
    return "\n".join(lines) + "\n"


def _replace_odoo_tests_common_import(m: re.Match) -> str:
    """Replace 'from odoo.tests.common import ...' preserving HttpCase etc., dropping TransactionCase."""
    orig = m.group(1)
    parts = [p.strip() for p in re.split(r",\s*", orig) if p.strip()]
    rest = [p for p in parts if p != "TransactionCase"]
    if not rest:
        return "from odoo.addons.plasticos_base.test_common import PlasticosTestCase\n"
    lines = ["from odoo.addons.plasticos_base.test_common import PlasticosTestCase"]
    lines.append(f"from odoo.tests.common import {', '.join(rest)}")
    return "\n".join(lines) + "\n"


IMPORT_PATTERNS = [
    (
        re.compile(r"from odoo\.tests import (?:TransactionCase(?:,\s*tagged)?|tagged,\s*TransactionCase)\s*\n"),
        _replace_odoo_tests_import,
    ),
    (re.compile(r"from odoo\.tests\.common import ([^\n]+)\n"), _replace_odoo_tests_common_import),
]

# Class base patterns: (TransactionCase) or (TransactionCase, PlastOSTestFactoryMixin) or (TransactionCase, tagged)
CLASS_BASE_PATTERNS = [
    (re.compile(r"\(\s*TransactionCase\s*,\s*PlastOSTestFactoryMixin\s*\)"), "(PlasticosTestCase)"),
    (re.compile(r"\(\s*PlastOSTestFactoryMixin\s*,\s*TransactionCase\s*\)"), "(PlasticosTestCase)"),
    (re.compile(r"\(\s*TransactionCase\s*,\s*tagged\s*\)"), "(PlasticosTestCase, tagged)"),
    (re.compile(r"\(\s*tagged\s*,\s*TransactionCase\s*\)"), "(PlasticosTestCase, tagged)"),
    (re.compile(r"\(\s*TransactionCase\s*\)"), "(PlasticosTestCase)"),
]

# Remove PlastOSTestFactoryMixin import if present
REMOVE_IMPORT_PATTERNS = [
    re.compile(r"from \.common import PlastOSTestFactoryMixin\n"),
    re.compile(r"from \.\.common import PlastOSTestFactoryMixin\n"),
    re.compile(r"from tests\.common import PlastOSTestFactoryMixin\n"),
]


def should_skip(path: Path) -> bool:
    """Skip HttpCase-only files and plasticos_base/test_common.py itself."""
    if "common.py" in path.name:
        return True
    content = path.read_text(encoding="utf-8")
    # Skip if uses HttpCase and no TransactionCase
    if "HttpCase" in content and "TransactionCase" not in content:
        return True
    return False


def cleanup_redundant_setup(content: str) -> str:
    """Remove redundant setUpClass lines that duplicate PlasticosTestCase defaults."""
    # Only remove exact default patterns: _create_partner(), _get_or_create_polymer(), _get_or_create_form()
    # with no args. Replace with newline to preserve spacing.
    if "cls.partner = cls._create_partner()" in content:
        content = re.sub(r"^\s*cls\.partner\s*=\s*cls\._create_partner\(\)\s*\n", "\n", content, flags=re.MULTILINE)
        content = REPLACE_PARTNER.sub(r"\1.default_partner", content)
    if "cls.polymer = cls._get_or_create_polymer()" in content:
        content = re.sub(
            r"^\s*cls\.polymer\s*=\s*cls\._get_or_create_polymer\(\)\s*\n", "\n", content, flags=re.MULTILINE
        )
        content = REPLACE_POLYMER.sub(r"\1.default_polymer", content)
    if "cls.form = cls._get_or_create_form()" in content:
        content = re.sub(r"^\s*cls\.form\s*=\s*cls\._get_or_create_form\(\)\s*\n", "\n", content, flags=re.MULTILINE)
        content = REPLACE_FORM.sub(r"\1.default_form", content)
    return content


def _already_migrated(content: str) -> bool:
    """True if file already uses PlasticosTestCase and has no TransactionCase in code."""
    if "PlasticosTestCase" not in content:
        return False
    # TransactionCase in class bases or imports = not migrated
    if re.search(r"class\s+\w+\([^)]*TransactionCase", content):
        return False
    if re.search(r"from\s+odoo\.(tests|tests\.common)\s+import[^\n]*TransactionCase", content):
        return False
    return True


def _safe_write(path: Path, content: str) -> None:
    """Write only to files contained inside the repository root (path-traversal guard)."""
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ValueError(f"Refusing to write outside repo root: {resolved}")
    resolved.write_text(content, encoding="utf-8")


def migrate_file(path: Path, dry_run: bool, cleanup: bool = False) -> bool:
    """Apply migration to a single file. Returns True if changed."""
    content = path.read_text(encoding="utf-8")
    if _already_migrated(content):
        if cleanup:
            cleaned = cleanup_redundant_setup(content)
            if cleaned != content:
                if not dry_run:
                    _safe_write(path, cleaned)
                return True
        return False
    if should_skip(path):
        return False

    original = content

    # 1. Replace imports (replacement may be a string or a callable; re.sub handles both)
    for pattern, replacement in IMPORT_PATTERNS:
        content = pattern.sub(replacement, content)

    # 2. Remove PlastOSTestFactoryMixin imports
    for pat in REMOVE_IMPORT_PATTERNS:
        content = pat.sub("", content)

    # 3. Replace class bases
    for pattern, replacement in CLASS_BASE_PATTERNS:
        content = pattern.sub(replacement, content)

    # 4. Cleanup redundant setup (when --cleanup)
    if cleanup:
        content = cleanup_redundant_setup(content)

    if content != original:
        if not dry_run:
            _safe_write(path, content)
        return True
    return False


def collect_files() -> list[Path]:
    """Collect all plasticos test files and root tests."""
    files: list[Path] = []
    for p in REPO_ROOT.glob(PLASTICOS_PATTERN):
        files.append(p)
    for p in REPO_ROOT.glob(PLASTICOS_BASE_PATTERN):
        if p not in files:
            files.append(p)
    for p in REPO_ROOT.glob(ROOT_TESTS_PATTERN):
        txt = p.read_text(encoding="utf-8")
        if "plasticos" in str(p) or "TransactionCase" in txt or "PlasticosTestCase" in txt:
            files.append(p)
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate plasticos tests to PlasticosTestCase")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--cleanup", action="store_true", help="Also remove redundant setUpClass code")
    args = parser.parse_args()

    files = collect_files()
    changed: list[Path] = []
    for path in files:
        if migrate_file(path, args.dry_run, cleanup=args.cleanup):
            changed.append(path)

    if args.dry_run:
        print("DRY RUN - no files written")
    print(f"{'Migrated' if not args.cleanup else 'Migrated+cleaned'} {len(changed)} files:")
    for p in changed:
        rel = p.relative_to(REPO_ROOT)
        print(f"  {rel}")


if __name__ == "__main__":
    main()

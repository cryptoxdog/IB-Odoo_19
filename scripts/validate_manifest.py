#!/usr/bin/env python3
"""Validate a single __manifest__.py file. Exit 0 if OK, 1 on error."""

import ast
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: validate_manifest.py <path-to-__manifest__.py>")
    sys.exit(1)

# Containment guard: the CLI path must resolve inside the working tree
# (SonarCloud S8707 — no path traversal via argv).
manifest_path = Path(sys.argv[1]).resolve()
if not manifest_path.is_relative_to(Path.cwd().resolve()):
    print(f"  ERROR: manifest path escapes the working tree: {manifest_path}")
    sys.exit(1)

try:
    with open(manifest_path) as f:
        content = f.read()
    manifest_dict = ast.literal_eval(content)
except Exception:
    print("  ERROR: Cannot parse manifest as dict")
    sys.exit(1)

required_fields = ["name", "version", "depends"]
missing = [f for f in required_fields if f not in manifest_dict]
if missing:
    print(f"  ERROR: Missing required fields: {missing}")
    sys.exit(1)

version = manifest_dict.get("version", "")
if not version.startswith("19.0."):
    print(f"  WARNING: Version '{version}' should start with '19.0.' for Odoo 19")

license_val = manifest_dict.get("license", "")
valid_licenses = ["LGPL-3", "AGPL-3", "GPL-3", "Other proprietary"]
if license_val and license_val not in valid_licenses:
    print(f"  WARNING: License '{license_val}' is non-standard")

print("  OK")

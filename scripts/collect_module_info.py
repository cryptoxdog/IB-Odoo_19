#!/usr/bin/env python3
"""Print module info for a manifest. Used by release workflow."""

import ast
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("Usage: collect_module_info.py <manifest-path> <module-name>")
    sys.exit(1)

# Containment guard: the CLI path must resolve inside the working tree
# (SonarCloud S8707 — no path traversal via argv).
manifest_path = Path(sys.argv[1]).resolve()
if not manifest_path.is_relative_to(Path.cwd().resolve()):
    print(f"Error: manifest path escapes the working tree: {manifest_path}")
    sys.exit(1)
module_name = sys.argv[2]

with open(manifest_path) as f:
    m = ast.literal_eval(f.read())

print(f"### {m.get('name', module_name)}")
print(f"- **Technical Name**: {module_name}")
print(f"- **Version**: {m.get('version', 'N/A')}")
print(f"- **Summary**: {m.get('summary', 'N/A')}")
print(f"- **Dependencies**: {', '.join(m.get('depends', []))}")
print("")

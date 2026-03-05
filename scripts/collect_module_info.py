#!/usr/bin/env python3
"""Print module info for a manifest. Used by release workflow."""

import ast
import sys

if len(sys.argv) < 3:
    print("Usage: collect_module_info.py <manifest-path> <module-name>")
    sys.exit(1)

manifest_path = sys.argv[1]
module_name = sys.argv[2]

with open(manifest_path) as f:
    m = ast.literal_eval(f.read())

print(f"### {m.get('name', module_name)}")
print(f"- **Technical Name**: {module_name}")
print(f"- **Version**: {m.get('version', 'N/A')}")
print(f"- **Summary**: {m.get('summary', 'N/A')}")
print(f"- **Dependencies**: {', '.join(m.get('depends', []))}")
print("")

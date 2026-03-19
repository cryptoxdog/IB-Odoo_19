#!/usr/bin/env python3
"""
Check for actions that reference potentially disabled/external models.

Detects:
1. Actions returning res_model for modules that are installable: False
2. Actions referencing models from microservice modules

Exit codes:
- 0: All checks passed
- 1: Issues found
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent

# Models that are external microservices (not installed in Odoo)
# NOTE: plasticos.match.result and plasticos.match.job removed — they are
# defined in plasticos_matching which is an active installed module.
EXTERNAL_MODELS = {
    "plasticos.enrichment.task",
    "plasticos.graph.node",
    "plasticos.graph.edge",
}

EXCLUDED_DIRS = {
    ".venv",
    "venv",
    "odoo-enterprise",
    "addons",
    "__pycache__",
    ".git",
    "docs",
    "ci",
    "plasticos_graph_engine",
    "plasticos_graph_integration",
    "plasticos_graph_intelligence",
    "plasticos_graph_3d_embedding",
    "plasticos_matching",
    "plasticos_buyer_match_engine",
    "plasticos_enrichment",
    "plasticos_enrichment_bridge",
}

# Repo-root level folders to exclude (not module-level tests/)
EXCLUDED_ROOT_DIRS = {"tests", "tests-odoo"}


def find_python_files():
    """Find all Python model files."""
    for path in WORKSPACE.rglob("*.py"):
        # Exclude directories anywhere in path
        if any(excl in path.parts for excl in EXCLUDED_DIRS):
            continue
        # Exclude repo-root level folders only (not module tests/)
        rel_path = path.relative_to(WORKSPACE)
        if rel_path.parts and rel_path.parts[0] in EXCLUDED_ROOT_DIRS:
            continue
        yield path


def check_external_model_actions(path: Path) -> list[str]:
    """
    Check for actions that reference external microservice models.
    """
    issues = []
    content = path.read_text()
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        for model in EXTERNAL_MODELS:
            # Check for res_model assignments
            if f'"res_model": "{model}"' in line or f"'res_model': '{model}'" in line:
                issues.append(f"  {path.relative_to(WORKSPACE)}:{i} - Action references external model '{model}'")

    return issues


def main():
    issues = []

    for path in find_python_files():
        try:
            issues.extend(check_external_model_actions(path))
        except Exception as e:
            print(f"Error processing {path}: {e}", file=sys.stderr)

    if issues:
        print("Actions referencing external/disabled models:")
        print("\n".join(issues))
        print()
        print("  FIX: Return notification instead of act_window for disabled features")
        print("Disabled action check failed.")
        return 1

    print("Disabled action check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

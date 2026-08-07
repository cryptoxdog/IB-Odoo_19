"""Shared filesystem skips for local audit scanners."""

from __future__ import annotations

from pathlib import Path

SKIP_DIR_PARTS = frozenset(
    {
        "odoo-enterprise",
        "odoo",
        "odoo-source",
        ".venv",
        "venv",
        "node_modules",
        "Current Work - IGNORE",
        "skills",
        "scripts",
        "tools",
        "__pycache__",
        ".git",
    }
)


def skip_path(path: Path | str) -> bool:
    """Return True when path is under a non-addon / gitignored tree."""
    return any(part in SKIP_DIR_PARTS for part in Path(path).parts)

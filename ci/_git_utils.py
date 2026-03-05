#!/usr/bin/env python3
"""
Git utility functions for CI scripts.

All CI scripts should use these functions to ensure they only scan
git-tracked files (respecting .gitignore).
"""

import subprocess
from pathlib import Path


def get_git_tracked_files(pattern: str = "", root_dir: Path | None = None) -> list[Path]:
    """
    Get git-tracked files matching pattern.

    Args:
        pattern: Git ls-files pattern (e.g., "*.py", "*/models/*.py")
        root_dir: Root directory to run git command from (defaults to cwd)

    Returns:
        List of Path objects for tracked files
    """
    try:
        cmd = ["git", "ls-files"]
        if pattern:
            cmd.append(pattern)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=root_dir,
        )
        files = [Path(f) for f in result.stdout.strip().split("\n") if f]
        return files
    except subprocess.CalledProcessError:
        return []


def get_git_tracked_dirs(pattern: str = "plasticos_*", root_dir: Path | None = None) -> list[Path]:
    """
    Get git-tracked directories matching pattern.

    Args:
        pattern: Directory pattern (e.g., "plasticos_*")
        root_dir: Root directory (defaults to cwd)

    Returns:
        List of Path objects for directories containing tracked files
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", f"{pattern}/*"],
            capture_output=True,
            text=True,
            check=True,
            cwd=root_dir,
        )
        # Extract unique directory names from file paths
        dirs = set()
        for f in result.stdout.strip().split("\n"):
            if f and "/" in f:
                # Get first directory component matching pattern
                parts = f.split("/")
                if parts[0].startswith(pattern.replace("*", "")):
                    dir_path = Path(parts[0])
                    if root_dir:
                        dir_path = root_dir / dir_path
                    dirs.add(dir_path)
        return sorted(dirs)
    except subprocess.CalledProcessError:
        return []


def is_git_tracked(file_path: Path, root_dir: Path | None = None) -> bool:
    """
    Check if a file is tracked by git.

    Args:
        file_path: Path to check
        root_dir: Root directory (defaults to cwd)

    Returns:
        True if file is tracked, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(file_path)],
            capture_output=True,
            text=True,
            cwd=root_dir,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False


def get_git_root() -> Path | None:
    """Get the root directory of the git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None

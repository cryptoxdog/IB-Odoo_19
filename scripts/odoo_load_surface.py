#!/usr/bin/env python3
"""Single owner of the Odoo install load surface for PlasticOS.

The load surface is the set of repository files whose bytes can change what
``odoo-bin -i <plasticos modules> --without-demo=all --stop-after-init`` loads.
It is the only definition install-smoke evidence, the installer, and pr-check
gate selection may use; nothing else re-derives "which files does Odoo read".

Per addon directory ``plasticos_*`` with a ``__manifest__.py``:

* ``__manifest__.py`` itself (Odoo parses every manifest on the addons path,
  installable or not).
* For installable addons: every ``*.py`` except the ``tests/`` subpackage
  (``odoo.addons.<name>`` imports the package; ``tests`` is imported only
  under ``--test-enable``, which install-smoke does not pass).
* Every file named in the manifest ``data`` list, and in the legacy
  ``init_xml`` / ``update_xml`` lists when present. A declared file that does
  not exist is an error, never a silent skip.
* ``i18n/**`` (translations are loaded for active languages at install).
* ``static/**`` (declared assets are registered at install; kept conservatively).
* ``demo`` files are excluded: the installer passes ``--without-demo=all``.

Installer inputs (repository-relative): ``config/**``, ``.env``,
``requirements.txt``, ``constraints.txt``, ``docker-compose.yml``,
``docker-compose.yaml``, ``Dockerfile``, ``scripts/install_smoke.sh``,
``scripts/get_odoo_module_order.py`` and this file.

Every path is discovered by walking the filesystem, so tracked, untracked and
ignored files are all part of the surface. Metadata directories are skipped.

Usage::

    python3 scripts/odoo_load_surface.py --list [--root DIR] [-0]
    python3 scripts/odoo_load_surface.py --classify PATH... [--root DIR]
    python3 scripts/odoo_load_surface.py --json [--root DIR]

``--classify`` prints ``<class>\t<path>`` per argument with class
``load_surface``, ``installer`` or ``other`` and exits 3 when at least one
path is ``load_surface`` or ``installer`` (0 otherwise). Paths are taken
relative to the root; absolute paths are accepted when they lie under it.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

EXCLUDED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
ADDON_PREFIX = "plasticos_"
MANIFEST = "__manifest__.py"
DATA_KEYS = ("data", "init_xml", "update_xml")
DEMO_KEYS = ("demo", "demo_xml")
INSTALLER_FILES = (
    ".env",
    "requirements.txt",
    "constraints.txt",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "scripts/install_smoke.sh",
    "scripts/get_odoo_module_order.py",
    "scripts/odoo_load_surface.py",
)
INSTALLER_DIRS = ("config",)


class LoadSurfaceError(RuntimeError):
    """A manifest cannot be read or declares a file that does not exist."""


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _walk_files(directory: Path) -> list[Path]:
    found: list[Path] = []
    for current, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in sorted(files):
            path = Path(current) / name
            if path.is_file():
                found.append(path)
    return found


def _read_manifest(path: Path) -> dict:
    try:
        node = ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as exc:
        raise LoadSurfaceError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(node, dict):
        raise LoadSurfaceError(f"manifest is not a dict literal: {path}")
    return node


def _declared(manifest: dict, keys: tuple[str, ...], addon: Path, root: Path) -> list[Path]:
    paths: list[Path] = []
    for key in keys:
        entries = manifest.get(key) or []
        if not isinstance(entries, (list, tuple)):
            raise LoadSurfaceError(f"manifest key {key!r} is not a list in {_rel(addon, root)}")
        for entry in entries:
            if not isinstance(entry, str) or not entry:
                raise LoadSurfaceError(f"manifest key {key!r} has a non-string entry in {_rel(addon, root)}")
            target = (addon / entry).resolve()
            if addon.resolve() not in target.parents:
                raise LoadSurfaceError(f"declared file escapes its addon: {entry} in {_rel(addon, root)}")
            if not target.is_file():
                raise LoadSurfaceError(f"declared file missing: {entry} in {_rel(addon, root)}")
            paths.append(target)
    return paths


def addon_dirs(root: Path) -> list[Path]:
    return sorted(
        p for p in root.iterdir() if p.is_dir() and p.name.startswith(ADDON_PREFIX) and (p / MANIFEST).is_file()
    )


def addon_surface(addon: Path, root: Path) -> set[Path]:
    manifest_path = addon / MANIFEST
    surface: set[Path] = {manifest_path}
    manifest = _read_manifest(manifest_path)
    if manifest.get("installable", True) is False:
        return surface
    tests_dir = addon / "tests"
    for path in _walk_files(addon):
        if path.suffix == ".py" and tests_dir not in path.parents:
            surface.add(path)
    surface.update(_declared(manifest, DATA_KEYS, addon, root))
    for sub in ("i18n", "static"):
        directory = addon / sub
        if directory.is_dir():
            surface.update(_walk_files(directory))
    return surface


def installer_surface(root: Path) -> set[Path]:
    surface: set[Path] = set()
    for rel in INSTALLER_FILES:
        path = root / rel
        if path.is_file():
            surface.add(path)
    for rel in INSTALLER_DIRS:
        directory = root / rel
        if directory.is_dir():
            surface.update(_walk_files(directory))
    return surface


def load_surface(root: Path) -> tuple[list[str], list[str]]:
    """Return (addon load-surface paths, installer input paths), repository-relative and sorted."""
    root = root.resolve()
    addon_paths: set[Path] = set()
    for addon in addon_dirs(root):
        addon_paths.update(addon_surface(addon, root))
    installer_paths = installer_surface(root)
    return (
        sorted(_rel(p, root) for p in addon_paths),
        sorted(_rel(p, root) for p in installer_paths),
    )


def classify(root: Path, candidates: list[str]) -> list[tuple[str, str]]:
    root = root.resolve()
    addons, installer = load_surface(root)
    addon_set, installer_set = set(addons), set(installer)
    rows: list[tuple[str, str]] = []
    for raw in candidates:
        path = Path(raw)
        if path.is_absolute():
            try:
                rel = path.resolve().relative_to(root).as_posix()
            except ValueError:
                rows.append(("other", raw))
                continue
        else:
            rel = path.as_posix()
        if rel in addon_set:
            rows.append(("load_surface", rel))
        elif rel in installer_set:
            rows.append(("installer", rel))
        elif (root / rel).exists():
            rows.append(("other", rel))
        else:
            rows.append((_class_of_missing(rel), rel))
    return rows


def _class_of_missing(rel: str) -> str:
    """A path that is no longer on disk cannot be hashed; classify by shape so a deleted load file still counts."""
    parts = rel.split("/")
    if rel in INSTALLER_FILES or (parts and parts[0] in INSTALLER_DIRS):
        return "installer"
    if parts[0].startswith(ADDON_PREFIX) and len(parts) > 1:
        if parts[1] == "tests":
            return "other"
        if parts[-1] == MANIFEST or rel.endswith(".py") or parts[1] in ("i18n", "static"):
            return "load_surface"
        if rel.endswith((".xml", ".csv")):
            # A removed data file is only material when a manifest still names it;
            # that manifest is then unreadable-at-install, which _declared() rejects.
            return "load_surface"
    return "other"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Odoo install load surface for PlasticOS addons")
    parser.add_argument("--root", default=None, help="repository root (default: parent of this script's directory)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="print every load-surface and installer path")
    mode.add_argument("--json", action="store_true", help="print {addons: [...], installer: [...]} as JSON")
    mode.add_argument(
        "--classify", nargs="+", metavar="PATH", help="classify paths; exit 3 if any is load_surface/installer"
    )
    parser.add_argument("-0", dest="nul", action="store_true", help="NUL-separate --list output")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    try:
        if args.classify:
            rows = classify(root, args.classify)
            for cls, rel in rows:
                print(f"{cls}\t{rel}")
            return 3 if any(cls != "other" for cls, _ in rows) else 0
        addons, installer = load_surface(root)
    except LoadSurfaceError as exc:
        print(f"odoo_load_surface: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"addons": addons, "installer": installer}, indent=2))
        return 0
    sep = "\0" if args.nul else "\n"
    sys.stdout.write(sep.join(addons + installer) + (sep if addons or installer else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

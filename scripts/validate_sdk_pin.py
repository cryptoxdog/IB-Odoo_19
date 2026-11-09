#!/usr/bin/env python3
"""Fail closed unless every Gate_SDK declaration is the moving major channel ``v1``.

Gate_SDK owns release identity (``contracts/RELEASE_IDENTITY_LEDGER.json``,
schema v2). Its consumer contract is the moving major channel ``v1``: consumers
declare that channel and never a commit sha, ``main``/``master``, or a fork.
Gate, EIE and CEG already declare it. The 2026-11-08 amendment to
``docs/adr/gate-integration/ADR-011-exact-sdk-revision-pins.md`` moves
PlasticOS onto the same channel (operator decision: float on ``@v1``).

``requirements.txt`` is the one declaring surface. Odoo.sh installs it, the
Dockerfile installs it, and the CI ``gate-sdk-tests`` job installs exactly its
``constellation-node-sdk`` line. Any other file that names a Gate_SDK git ref
(a workflow, a Dockerfile, another requirements file) is scanned too, so a
second identity cannot appear somewhere this check does not look.

The previous version of this script required ``92279da`` (a revision older
than ``GateClient.execute()``) and nothing invoked it.
``tests/test_validate_sdk_pin.py`` runs it against the tree.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAJOR_TAG = "v1"
CANONICAL_REPO = "Quantum-L9/Gate_SDK"
FORBIDDEN_FORK = "cryptoxdog/Gate_SDK"
FORBIDDEN_BRANCHES = ("main", "master")

DECLARING_SURFACE = "requirements.txt"
# Files that could install the SDK directly. Each is optional, but a Gate_SDK
# ref found in one must still be the channel.
SCANNED_GLOBS = (
    "requirements*.txt",
    "constraints.txt",
    "Dockerfile*",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
)

SHA_RE = re.compile(r"[0-9a-f]{7,40}")
REF_RE = re.compile(r"Gate_SDK(?:\.git)?@([0-9A-Za-z._/-]+)")
REQUIREMENT_RE = re.compile(
    r"^constellation-node-sdk @ git\+https://github\.com/(?P<repo>[^@\s]+?)(?:\.git)?@(?P<ref>\S+)\s*$"
)


def check_refs(rel: str, text: str) -> list[str]:
    """Every Gate_SDK ref named in *text* is the channel; no fork appears."""
    errors: list[str] = []
    if FORBIDDEN_FORK in text:
        errors.append(f"{rel}: forbidden fork {FORBIDDEN_FORK}")
    for ref in REF_RE.findall(text):
        if ref == MAJOR_TAG:
            continue
        if SHA_RE.fullmatch(ref):
            errors.append(
                f"{rel}: Gate_SDK declared by commit sha {ref}; the consumer contract is the moving major channel {MAJOR_TAG}"
            )
        elif ref in FORBIDDEN_BRANCHES:
            errors.append(f"{rel}: Gate_SDK floats on branch {ref!r}")
        else:
            errors.append(f"{rel}: Gate_SDK ref {ref!r} is not {MAJOR_TAG!r}")
    return errors


def check_declaration(rel: str, text: str) -> list[str]:
    """The declaring surface holds exactly one canonical channel requirement."""
    lines = [line for line in text.splitlines() if line.startswith("constellation-node-sdk")]
    if len(lines) != 1:
        return [f"{rel}: expected exactly one constellation-node-sdk requirement, found {len(lines)}"]
    match = REQUIREMENT_RE.match(lines[0])
    if match is None:
        return [f"{rel}: constellation-node-sdk is not a git requirement on {CANONICAL_REPO}: {lines[0]!r}"]
    errors: list[str] = []
    if match.group("repo") != CANONICAL_REPO:
        errors.append(f"{rel}: constellation-node-sdk comes from {match.group('repo')}, not {CANONICAL_REPO}")
    if match.group("ref") != MAJOR_TAG:
        errors.append(f"{rel}: constellation-node-sdk ref {match.group('ref')!r} is not {MAJOR_TAG!r}")
    return errors


def check_tree(root: Path) -> list[str]:
    errors: list[str] = []
    declaring = root / DECLARING_SURFACE
    if not declaring.is_file():
        return [f"{DECLARING_SURFACE}: declaring surface is missing"]
    errors.extend(check_declaration(DECLARING_SURFACE, declaring.read_text(encoding="utf-8")))

    scanned = sorted({path for pattern in SCANNED_GLOBS for path in root.glob(pattern) if path.is_file()})
    for path in scanned:
        rel = path.relative_to(root).as_posix()
        errors.extend(check_refs(rel, path.read_text(encoding="utf-8")))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Gate_SDK moving-major declaration.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    errors = check_tree(args.root)
    if errors:
        print("FAIL")
        print("\n".join(errors))
        return 1
    print(f"PASS PlasticOS declares {CANONICAL_REPO}@{MAJOR_TAG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

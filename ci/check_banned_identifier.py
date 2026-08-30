#!/usr/bin/env python3
"""BAN001 — legacy vendor identifier prohibition guard.

Canonical enforcement for INVARIANTS.md invariant 20. CI and local validation
both invoke THIS script; the matching logic exists exactly once, here.

The prohibited byte sequence is never spelled literally in this file (that would
itself violate the policy it enforces). It is reconstructed at runtime from its
ASCII code points, so this guard is self-clean by construction.

Checks every tracked entry, with no exclusion list, no allowlist, no ignore
comment, and no generated-file exemption:

  * tracked path names, including every implicit directory component
  * symlink target strings
  * raw bytes of every tracked regular file (text AND binary)

Exit status: 0 only when the repository is clean; 1 on any violation; 2 on any
condition that prevents a complete verdict (fail closed).
"""

from __future__ import annotations

import os
import subprocess
import sys

# BAN001 reconstructed from ASCII code points — never written contiguously.
BANNED = bytes([99, 105, 101, 116, 114, 97, 100, 101])
BANNED_STR = BANNED.decode("ascii")
POLICY_ID = "BAN001"

_CHUNK = 1 << 20  # 1 MiB
_OVERLAP = len(BANNED) - 1


def _run(args: list[str]) -> bytes:
    proc = subprocess.run(args, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(
            f"{POLICY_ID}: FAIL-CLOSED: command failed: {' '.join(args)}\n{proc.stderr.decode('utf-8', 'replace')}\n"
        )
        raise SystemExit(2)
    return proc.stdout


def tracked_entries() -> list[tuple[str, str]]:
    """Return (mode, path) for every tracked entry, NUL-safe."""
    out = _run(["git", "ls-files", "-sz"])
    entries: list[tuple[str, str]] = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        if not path:
            sys.stderr.write(f"{POLICY_ID}: FAIL-CLOSED: unparsable index record: {rec!r}\n")
            raise SystemExit(2)
        mode = meta.split(b" ", 1)[0].decode("ascii", "replace")
        entries.append((mode, path.decode("utf-8", "surrogateescape")))
    return entries


def path_violation(path: str) -> str | None:
    """Report the first path component carrying the banned sequence."""
    for component in path.split("/"):
        if BANNED_STR in component.lower():
            return component
    return None


def file_contains(path: str) -> bool:
    """Stream raw bytes; overlap keeps a match across a chunk seam detectable."""
    carry = b""
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                return False
            if BANNED in (carry + chunk).lower():
                return True
            carry = chunk[-_OVERLAP:] if _OVERLAP else b""


def main() -> int:
    violations: list[str] = []

    for mode, path in tracked_entries():
        component = path_violation(path)
        if component is not None:
            kind = "directory name" if component != path.rsplit("/", 1)[-1] else "file name"
            violations.append(f"{path}: prohibited sequence in {kind} component {component!r}")

        if mode == "120000" or os.path.islink(path):
            # Read the target from the index blob, not the worktree: a tracked
            # symlink that is not currently materialised must still be inspected,
            # otherwise a committed prohibited target could evade the guard.
            target = _run(["git", "cat-file", "blob", f":{path}"]).decode("utf-8", "surrogateescape")
            if BANNED_STR in target.lower():
                violations.append(f"{path}: prohibited sequence in symlink target {target!r}")
            continue

        if not os.path.isfile(path):
            sys.stderr.write(f"{POLICY_ID}: FAIL-CLOSED: tracked file missing from worktree: {path}\n")
            return 2

        try:
            if file_contains(path):
                violations.append(f"{path}: prohibited sequence in file content")
        except OSError as exc:
            sys.stderr.write(f"{POLICY_ID}: FAIL-CLOSED: unreadable tracked file {path}: {exc}\n")
            return 2

    if violations:
        sys.stderr.write(
            f"\n{POLICY_ID} VIOLATION: the prohibited legacy vendor identifier is present "
            f"in {len(violations)} location(s).\n"
            "See INVARIANTS.md invariant 20. There is no exclusion mechanism: remove the\n"
            "sequence at its canonical source (regenerate generated artifacts rather than\n"
            "hand-patching them).\n\n"
        )
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        sys.stderr.write("\n")
        return 1

    print(f"{POLICY_ID}: OK — no prohibited identifier in tracked paths, symlinks, or content.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

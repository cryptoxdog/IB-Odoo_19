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

import subprocess
import sys

# BAN001 reconstructed from ASCII code points — never written contiguously.
BANNED = bytes([99, 105, 101, 116, 114, 97, 100, 101])
BANNED_STR = BANNED.decode("ascii")
POLICY_ID = "BAN001"


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


def read_blobs(paths: list[str]) -> dict[str, bytes]:
    """Read every tracked blob from the git index in one batch.

    The index, not the worktree, is the authority for "tracked content": it is
    what a commit will contain, and it stays readable when a tracked file is
    absent from a dirty worktree. Symlink targets are read the same way, so the
    guard has exactly one notion of what it is inspecting.
    """
    if not paths:
        return {}
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch", "-z"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    query = b"".join(b":" + p.encode("utf-8", "surrogateescape") + b"\0" for p in paths)
    out, err = proc.communicate(query)
    if proc.returncode != 0:
        sys.stderr.write(f"{POLICY_ID}: FAIL-CLOSED: git cat-file failed: {err.decode('utf-8', 'replace')}\n")
        raise SystemExit(2)

    blobs: dict[str, bytes] = {}
    pos = 0
    for path in paths:
        nl = out.find(b"\n", pos)
        if nl == -1:
            sys.stderr.write(f"{POLICY_ID}: FAIL-CLOSED: truncated cat-file stream at {path}\n")
            raise SystemExit(2)
        header = out[pos:nl].decode("utf-8", "replace")
        parts = header.split(" ")
        if len(parts) != 3 or parts[1] != "blob":
            sys.stderr.write(f"{POLICY_ID}: FAIL-CLOSED: unreadable tracked object {path}: {header}\n")
            raise SystemExit(2)
        size = int(parts[2])
        start = nl + 1
        blobs[path] = out[start : start + size]
        pos = start + size + 1  # trailing newline after payload
    return blobs


def main() -> int:
    violations: list[str] = []
    entries = tracked_entries()

    # Gitlinks (submodule pointers) carry no blob of their own; their contents
    # belong to the submodule's repository, not this index.
    inspectable = [(mode, path) for mode, path in entries if mode != "160000"]
    blobs = read_blobs([path for _, path in inspectable])

    for mode, path in inspectable:
        component = path_violation(path)
        if component is not None:
            kind = "directory name" if component != path.rsplit("/", 1)[-1] else "file name"
            violations.append(f"{path}: prohibited sequence in {kind} component {component!r}")

        blob = blobs.get(path)
        if blob is None:
            sys.stderr.write(f"{POLICY_ID}: FAIL-CLOSED: no tracked content for {path}\n")
            return 2

        if mode == "120000":
            target = blob.decode("utf-8", "surrogateescape")
            if BANNED_STR in target.lower():
                violations.append(f"{path}: prohibited sequence in symlink target {target!r}")
            continue

        if BANNED in blob.lower():
            violations.append(f"{path}: prohibited sequence in file content")

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

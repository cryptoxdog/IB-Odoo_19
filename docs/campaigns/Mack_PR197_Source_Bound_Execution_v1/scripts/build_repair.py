#!/usr/bin/env python3
"""Source-bound four-file Mack PR #197 repair. No network, push or merge."""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

REPO = "cryptoxdog/IB-Odoo_19"
HEAD = "7dcada49fd301d3b5dafb30405d0242667915fbe"
MODEL = "plasticos_mack_workbench/models/internal_review.py"
MODEL_SHA = "d17eba9c3599aeaa077b7cdd28d87c3667bc3890"
TEST = "plasticos_mack_workbench/tests/test_internal_review.py"
TEST_SHA = "c8bf98419ce8528e2707ecb03adf846cc44223d0"
MANIFEST = "plasticos_mack_workbench/__manifest__.py"
MANIFEST_SHA = "7ce7e542af8ec4f9d2bb6976cdcff66d342d4148"
OLD_VERSION = '    "version": "19.0.1.1.0",'
NEW_VERSION = '    "version": "19.0.1.1.1",'
HELPER = "tests/runtime_gates/_runtime_env.py"

BAD_VALIDATOR = 'if not _SHA256_RE.fullmatch((record.decision_snapshot_hash or "").strip()):'
GOOD_VALIDATOR = 'if not _SHA256_RE.fullmatch(record.decision_snapshot_hash or ""):'
TEST_ANCHOR = "    def test_identical_retry_returns_prior_receipt_without_second_activity(self):\n"

TEST_ADDITION = """    def test_snapshot_hash_requires_exact_lowercase_sha256_without_whitespace(self):
        intake = self._canonical_intake()
        valid_hash = "a" * 64
        for index, malformed in enumerate(
            (f" {valid_hash}", f"{valid_hash} ", f" {valid_hash} ", valid_hash.upper())
        ):
            values = self._request_values(intake, key=f"mack-review-digest-invalid-{index}")
            values["decision_snapshot_hash"] = malformed
            with self.subTest(index=index), self.assertRaises(ValidationError):
                self.Review.create(values)
            self.assertEqual(
                self.Review.search_count([("idempotency_key", "=", f"mack-review-digest-invalid-{index}")]),
                0,
            )

"""

HELPER_BODY = '''"""Mack-only, fail-closed Odoo runtime configuration for independent-session gates.

This is the missing import used by _mack_runtime.py and both Mack gates.
Do not route these destructive test fixtures to an unknown or production DB.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path

import psycopg2

DB = os.environ.get("SEAM_DB", "")
PG_HOST = os.environ.get("SEAM_PG_HOST", "/tmp")
PG_PORT = int(os.environ.get("SEAM_PG_PORT", "5433"))
PG_USER = os.environ.get("SEAM_PG_USER", "odoo")
_REPO = Path(__file__).resolve().parents[2]


def bind_config(config) -> None:
    """Bind one explicitly named local, owned disposable Mack database."""
    if re.fullmatch(r"odoo_test_mack_[a-z0-9_]{1,32}", DB) is None:
        raise SystemExit("Mack gates require explicit SEAM_DB=odoo_test_mack_<id>; no default DB")
    if PG_HOST not in ("localhost", "127.0.0.1") and not PG_HOST.startswith("/"):
        raise SystemExit("Mack gates require a local PostgreSQL socket or localhost")
    if not 1 <= PG_PORT <= 65535:
        raise SystemExit("Invalid SEAM_PG_PORT")
    specified_repo = Path(os.environ.get("SEAM_REPO", str(_REPO))).resolve()
    if specified_repo != _REPO:
        raise SystemExit("SEAM_REPO is not this Mack checkout")
    # Read the actual Postgres ownership marker before any gate writes fixtures.
    connection = psycopg2.connect(
        dbname=DB, host=PG_HOST, port=PG_PORT, user=PG_USER, connect_timeout=5
    )
    try:
        with connection.cursor() as cr:
            cr.execute(
                "SELECT coalesce(shobj_description(oid, 'pg_database'), '') "
                "FROM pg_database WHERE datname = current_database()"
            )
            row = cr.fetchone()
        marker = row[0] if row else ""
    finally:
        connection.close()
    if not (
        ("role=clone" in marker and "owner=" in marker)
        or ("mack_owned_disposable=1" in marker and "owner=" in marker)
    ):
        raise SystemExit("SEAM_DB is not an owner-marked disposable clone; no Mack gate will run")
    source_env = os.environ.get("SEAM_ODOO_SRC", "")
    if source_env:
        source = Path(source_env).resolve()
    else:
        matches = sorted(glob.glob("/opt/odoo-src/odoo-19.0*"))
        if not matches:
            raise SystemExit("Provide SEAM_ODOO_SRC (Odoo 19 checkout); no local source found")
        source = Path(matches[-1]).resolve()
    addons = source / "odoo" / "addons"
    if not addons.is_dir():
        raise SystemExit(f"Odoo 19 addons path not found: {addons}")
    config["db_host"] = PG_HOST
    config["db_port"] = PG_PORT
    config["db_user"] = PG_USER
    config["addons_path"] = f"{addons},{_REPO}"
'''


def call(root: Path, *argv: str) -> str:
    if not argv or argv[0] != "git":
        raise RuntimeError("refusing a command that is not git")
    p = subprocess.run(["git", *argv[1:]], cwd=root, text=True, capture_output=True, check=False)  # noqa: S603, S607
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)} failed ({p.returncode}): {p.stderr.strip()}")
    return p.stdout.strip()


def ensure_target(root: Path) -> None:
    if not (root / ".git").exists() and call(root, "git", "rev-parse", "--is-inside-work-tree") != "true":
        raise RuntimeError("Expected a git worktree")
    actual_root = Path(call(root, "git", "rev-parse", "--show-toplevel")).resolve()
    if actual_root != root.resolve():
        raise RuntimeError("--repo must be the git worktree root")
    branch = call(root, "git", "branch", "--show-current")
    if branch != "mack":
        raise RuntimeError(f"Wrong source branch {branch!r}; expected 'mack'")
    head = call(root, "git", "rev-parse", "HEAD")
    if head != HEAD:
        raise RuntimeError(f"Stale PR source: HEAD {head}; expected {HEAD}")
    url = call(root, "git", "remote", "get-url", "origin")
    if not re.search(r"(?:github\.com[:/])cryptoxdog/IB-Odoo_19(?:\.git)?$", url):
        raise RuntimeError(f"Wrong origin; expected {REPO}: {url}")
    status = call(root, "git", "status", "--porcelain")
    if status:
        raise RuntimeError("Worktree not clean; refuse to overwrite user changes")
    for path, expected in ((MODEL, MODEL_SHA), (TEST, TEST_SHA), (MANIFEST, MANIFEST_SHA)):
        blob = call(root, "git", "hash-object", path)
        if blob != expected:
            raise RuntimeError(f"Source blob mismatch: {path}: {blob} != {expected}")
    if (root / HELPER).exists() or call(root, "git", "ls-files", "--", HELPER):
        raise RuntimeError(f"{HELPER} already exists; source state must be re-audited")


def replacements(model: str, test: str) -> tuple[str, str]:
    if model.count(BAD_VALIDATOR) != 1 or GOOD_VALIDATOR in model:
        raise RuntimeError("Exact model validation anchor unavailable or already changed")
    if test.count(TEST_ANCHOR) != 1 or "test_snapshot_hash_requires_exact_lowercase" in test:
        raise RuntimeError("Exact test anchor unavailable or already changed")
    model = model.replace(BAD_VALIDATOR, GOOD_VALIDATOR)
    test = test.replace(TEST_ANCHOR, TEST_ADDITION + TEST_ANCHOR)
    return model, test


def patch_file(path: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile="a/" + path, tofile="b/" + path
        )
    )


def make_patch(root: Path) -> str:
    model_old = (root / MODEL).read_text()
    test_old = (root / TEST).read_text()
    model_new, test_new = replacements(model_old, test_old)
    manifest_old = (root / MANIFEST).read_text()
    if manifest_old.count(OLD_VERSION) != 1 or NEW_VERSION in manifest_old:
        raise RuntimeError("Exact Mack module version anchor unavailable or already changed")
    manifest_new = manifest_old.replace(OLD_VERSION, NEW_VERSION)
    patch = patch_file(MODEL, model_old, model_new) + patch_file(TEST, test_old, test_new)
    patch += patch_file(MANIFEST, manifest_old, manifest_new)
    patch += "".join(
        difflib.unified_diff([], HELPER_BODY.splitlines(keepends=True), fromfile="/dev/null", tofile="b/" + HELPER)
    )
    return patch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="explicitly apply to clean, bound Mack checkout")
    args = parser.parse_args()
    root = args.repo.resolve()
    ensure_target(root)
    patch = make_patch(root)
    if not patch.endswith("\n"):
        raise RuntimeError("Generated patch must end in newline")
    if not args.output.is_absolute() and (root / args.output).resolve().is_relative_to(root):
        raise RuntimeError("Write patch outside worktree; worktree must stay clean")
    output = args.output.resolve()
    if output.is_relative_to(root):
        raise RuntimeError("Patch output must live outside target checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(patch)
    call(root, "git", "apply", "--check", str(output))
    if args.apply:
        call(root, "git", "apply", str(output))
        print("APPLIED: bounded Mack repair; repository changed locally, not committed or pushed")
    else:
        print("PASS: exact-head and blob binding, clean worktree, git apply --check")
    print(f"Patch: {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        sys.exit(1)

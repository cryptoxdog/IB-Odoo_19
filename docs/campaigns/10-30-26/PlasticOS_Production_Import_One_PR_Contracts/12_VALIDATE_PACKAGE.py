#!/usr/bin/env python3
"""Structural package validation, NOT CI/runtime/authority proof. Requires PyYAML."""

import hashlib
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
REQUIRED = {
    "contract_id",
    "objective",
    "target",
    "authority_refs",
    "in_scope",
    "out_of_scope",
    "locked_invariants",
    "acceptance_criteria",
    "forbidden_actions",
    "validation_obligations",
    "delivery_mode",
}
PHASES = [f"C{i:02}" for i in range(6)]


def check_contracts(files):
    errors = []
    ids = set()
    if len(files) != 6:
        errors.append("expected six phases")
    for i, p in enumerate(files):
        o = yaml.safe_load(p.read_text(encoding="utf8"))
        if not isinstance(o, dict):
            errors.append(f"{p.name}: not an object")
            continue
        missing = REQUIRED - set(o)
        if missing:
            errors.append(f"{p.name}: missing {missing}")
        if not str(o.get("contract_id", "")) or o.get("contract_id") in ids:
            errors.append(f"{p.name}: missing/duplicate id")
        ids.add(o.get("contract_id"))
        if not p.name.startswith(PHASES[i]):
            errors.append(f"{p.name}: order mismatch")
        target = o.get("target", {})
        if target.get("repository_or_artifact") != "https://github.com/cryptoxdog/IB-Odoo_19":
            errors.append(f"{p.name}: wrong repo")
        if not target.get("base_revision") or not target.get("branch_or_worktree"):
            errors.append(f"{p.name}: unbound target")
        for field in REQUIRED - {"objective", "contract_id", "target", "delivery_mode"}:
            if not isinstance(o.get(field), list) or not o[field]:
                errors.append(f"{p.name}: empty {field}")
        if "worksheet images" not in " ".join(o.get("out_of_scope", [])).lower():
            errors.append(f"{p.name}: documents not excluded")
        if "make pr" not in " ".join(o.get("forbidden_actions", [])).lower():
            errors.append(f"{p.name}: no publication guard")
    return errors


def main():
    files = sorted(ROOT.glob("C0*.yaml"))
    issues = check_contracts(files)
    wrapper = (ROOT / "00_DELEGATION_ONE_PR.md").read_text()
    if not wrapper.startswith("```yaml\nrepository_access:"):
        issues.append("repository access header not first")
    if "- https://github.com/cryptoxdog/IB-Odoo_19" not in wrapper:
        issues.append("missing one writable target")
    if any(bad in wrapper for bad in ["gh pr create", "git push --force"]):
        # Exact negated mentions are permissible; only reject if not negated.
        if "Do not call raw `git push`, `gh pr create`" not in wrapper:
            issues.append("unapproved publication surface")
    digests = []
    for line in (ROOT / "SHA256SUMS.txt").read_text().splitlines():
        if not line:
            continue
        sha, rel = line.split("  ", 1)
        path = ROOT / rel
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            issues.append(f"hash mismatch: {rel}")
        digests.append(rel)
    expected = set(p.name for p in ROOT.iterdir() if p.is_file()) - {"SHA256SUMS.txt"}
    if set(digests) != expected:
        issues.append(f"hash coverage mismatch: missing={expected - set(digests)} extra={set(digests) - expected}")
    print(json.dumps({"structural": "FAIL" if issues else "PASS", "errors": issues, "contracts": len(files)}, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())

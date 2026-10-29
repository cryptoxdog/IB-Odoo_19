#!/usr/bin/env python3
"""Validate bounded DR campaign-pack integrity, source coverage and owner mappings.

This checks the *delegation artifact*, not live AWS/Odoo/Infisical/1Password or
canonical L9 authority. No network calls or mutations.
"""

import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

EXPECTED_CONTRACTS = [
    "00_FEASIBILITY_AND_BLAST_RADIUS.md",
    "01_ODOO_NATIVE_BACKUP.md",
    "02_AWS_VAULT_AND_IDENTITY.md",
    "03_FULL_COPY_AND_INDEPENDENT_RESTORE.md",
    "04_INCREMENTAL_AND_WEEKDAY_SCHEDULE.md",
    "05_1PASSWORD_EMERGENCY_PACK.md",
    "06_ADVERSARIAL_REVIEW_AND_CLOSEOUT.md",
]
EXPECTED_INV = {f"DR-{i:03d}" for i in range(1, 50)}
ROOT_DIRS = ("architecture", "contracts", "coordination", "evidence", "operations", "policy", "security", "tools")


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def validate(root):
    root = Path(root)
    require((root / "MANIFEST.json").is_file(), "missing MANIFEST.json")
    manifest = json.loads((root / "MANIFEST.json").read_text("utf-8"))
    require(manifest["pack_id"] == "SM-ODOO-DR-CAMPAIGN-001" and manifest["version"] == "1.3.0", "wrong pack identity")
    records = manifest["files"]
    declared = [rec["path"] for rec in records]
    require(len(declared) == len(set(declared)), "duplicate manifest entry")
    require(all(not p.startswith("/") and ".." not in Path(p).parts for p in declared), "unsafe manifest path")
    skipped = {"MANIFEST.json", "CHECKSUMS.sha256"}
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    } - skipped
    require(
        actual == set(declared), f"inventory mismatch missing={set(declared) - actual} extra={actual - set(declared)}"
    )
    checksums = []
    for entry in records:
        rel = entry["path"]
        p = root / rel
        require(not p.is_symlink(), f"symlink forbidden: {rel}")
        data = p.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        require(len(data) == entry["bytes"] and digest == entry["sha256"], f"length/hash mismatch: {rel}")
        checksums.append(f"{digest}  {rel}")
    expected_lines = (root / "CHECKSUMS.sha256").read_text("utf-8").splitlines()
    require(len(expected_lines) == len(checksums) and expected_lines == checksums, "checksum manifest/order mismatch")
    require(
        manifest["file_count"] == len(records)
        and manifest["contract_count"] == 7
        and manifest["invariant_count"] == 49,
        "manifest count mismatch",
    )

    contracts = sorted(p.name for p in (root / "contracts").glob("*.md"))
    require(contracts == EXPECTED_CONTRACTS, "contract inventory/order mismatch")
    header = """```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
  unlisted_repositories: no_access
```"""
    for c in contracts:
        txt = (root / "contracts" / c).read_text("utf-8")
        require(txt.startswith(header), f"access boundary changed: {c}")
    require(
        (root / "coordination/CURSOR_START.md").read_text("utf-8").startswith(header), "starter access header changed"
    )

    policy = (root / "policy/LOCKED_POLICY.yaml").read_text("utf-8")
    require(
        "version: 1.3.0" in policy and "status: OPERATOR_LOCKED_NOT_IMPLEMENTED" in policy,
        "policy version/status missing",
    )
    for v in ("- '11:00'", "- '13:00'", "- '15:00'", "- '17:00'", "timezone: America/New_York"):
        require(v in policy, "locked schedule drift: " + v)
    require("00->01->02->03->05_baseline->04->05_refresh->06" in policy, "locked execution order drift")
    for k in (
        "operator_pack_as_soon_as_full_recovery_is_proven: true",
        "pinned_deployable_code_and_dependencies_independent_of_git_host: mandatory",
        "application_account_as_substitute: forbidden",
    ):
        require(k in policy, "locked dependency missing: " + k)

    inv_text = (root / "policy/INVARIANTS.md").read_text("utf-8")
    invs = {}
    for line in inv_text.splitlines():
        if not line.startswith("| **DR-"):
            continue
        cells = [s.strip() for s in line.strip().strip("|").split("|")]
        require(len(cells) == 3, "invariant table row corrupted")
        m = re.fullmatch(r"\*\*(DR-\d{3}) (.+)\*\*", cells[0])
        require(m, "bad invariant id")
        require(m.group(1) not in invs, "duplicate invariant: " + m.group(1))
        invs[m.group(1)] = (cells[1], cells[2])
    require(set(invs) == EXPECTED_INV, f"invariant census wrong: {set(invs) ^ EXPECTED_INV}")
    gate_text = (root / "evidence/ACCEPTANCE_MATRIX.md").read_text("utf-8")
    csv_p = root / "coordination/INVARIANT_TRACEABILITY.csv"
    trace = list(csv.DictReader(io.StringIO(csv_p.read_text("utf-8"))))
    require(len(trace) == 49 and {row["invariant_id"] for row in trace} == EXPECTED_INV, "traceability row/id mismatch")
    require(len({row["test_id"] for row in trace}) == 49, "duplicate test IDs")
    witness_txt = (root / "evidence/INVARIANT_TEST_WITNESSES.md").read_text("utf-8")
    headings = re.findall(
        r"^### (TI-\d{3}) \| (DR-\d{3}) \| Contract (\d{2}) \| Gate ([A-Za-z0-9-]+)$", witness_txt, re.M
    )
    require(len(headings) == 49 and len(set(headings)) == 49, "case headings missing or duplicated")
    expected_heads = set()
    for row in trace:
        invariant_id = row["invariant_id"]
        own = row["primary_contract"]
        gate = row["primary_gate"]
        case = row["test_id"]
        require(own in {f"{x:02d}" for x in range(7)}, "unrecognized contract owner " + invariant_id)
        require(case == f"TI-{int(invariant_id[-3:]):03d}", "wrong case id " + invariant_id)
        require(
            (row["proof_required"], row["falsifying_witness"]) == invs[invariant_id],
            "traceability witness not same as locked invariant " + invariant_id,
        )
        require(
            bool(re.search(r"^\|\s*\*{0,2}" + re.escape(gate) + r"(?:\s|\*|$)", gate_text, re.M)),
            "unresolved acceptance gate " + invariant_id + ": " + gate,
        )
        require(
            f"**Required PASS witness:** {row['proof_required']}" in witness_txt,
            "missing exact pass witness " + invariant_id,
        )
        require(
            f"**Fail if:** {row['falsifying_witness']}" in witness_txt, "missing exact negative witness " + invariant_id
        )
        expected_heads.add((case, invariant_id, own, gate))
    require(set(headings) == expected_heads, "case/owner/gate mismatch")

    # Every explicit, package-relative file reference in backticks must exist.
    bad = []
    rx = re.compile(r"`((?:" + "|".join(ROOT_DIRS) + r")/[A-Za-z0-9_./-]+\.(?:md|yaml|csv|json|py))`")
    for p in root.rglob("*.md"):
        for m in rx.finditer(p.read_text("utf-8")):
            if not (root / m.group(1)).is_file():
                bad.append((p.relative_to(root).as_posix(), m.group(1)))
    require(not bad, "unresolved bundled references " + repr(bad))
    for path in (
        "coordination/DEFINITION_OF_DONE.md",
        "coordination/CURSOR_START.md",
        "coordination/CAMPAIGN_ORDER.md",
        "contracts/03_FULL_COPY_AND_INDEPENDENT_RESTORE.md",
        "contracts/05_1PASSWORD_EMERGENCY_PACK.md",
        "security/INFISICAL_1PASSWORD_AND_CONFIG.md",
    ):
        require((root / path).is_file(), "missing required dependency " + path)
    order = (root / "coordination/CAMPAIGN_ORDER.md").read_text("utf-8")
    indices = [
        order.index(token)
        for token in ("00 prove exact", "03 one real", "05 initial:", "04 fresh,", "05 refresh:", "06 ransomware")
    ]
    require(indices == sorted(indices), "bad execution dependency order")
    require(
        "EARLY_INDEPENDENT_DAILY_PROTECTION" in (root / "coordination/DEFINITION_OF_DONE.md").read_text("utf-8"),
        "missing early protection gate",
    )
    require(
        "Odoo.sh, GitHub, Infisical, and the original Mac withheld"
        in (root / "contracts/03_FULL_COPY_AND_INDEPENDENT_RESTORE.md").read_text("utf-8"),
        "independent deployable code proof missing",
    )
    return f"STRUCTURAL_AND_TRACEABILITY_PASS | {len(records)} hashed payload files | 49 covered invariants | 7 contracts | {manifest['version']}"


def main():
    try:
        print(validate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]))
    except Exception as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

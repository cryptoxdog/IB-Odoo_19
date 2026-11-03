#!/usr/bin/env python3
"""Offline structure-only validator for a CRM Cursor evidence directory. No network/DB writes."""

import csv
import json
import sys
from pathlib import Path

TECH = {"PASS", "FAIL", "BLOCKED", "NOT_COLLECTED", "NOT_PROVEN", "NOT_APPLICABLE"}
BIZ = {"PASS", "FAIL", "NOT_PROVEN", "DEFERRED_APPROVED", "NOT_APPLICABLE"}
NEEDED = (
    "SESSION_SUMMARY.md",
    "COVERAGE_MATRIX.csv",
    "SOURCE_FIELD_LEDGER.csv",
    "SOURCE_CONTACT_CENSUS.csv",
    "ROOT_CAUSE_FINDINGS.md",
    "OPERATOR_DECISIONS.md",
    "BLOCKERS.md",
    "PROVENANCE.json",
    "NEXT_CODING_CONTRACT_CANDIDATES.md",
)


def csv_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    if len(sys.argv) != 2:
        print("usage: python3 validate_results.py <evidence-directory>", file=sys.stderr)
        return 2
    d = Path(sys.argv[1])
    base = Path(__file__).resolve().parent
    err = []
    for n in NEEDED:
        if not (d / n).is_file():
            err.append("missing " + n)
    if not (d / "COVERAGE_MATRIX.csv").exists():
        print("\n".join(err))
        return 1
    catalog = csv_rows(base / "CRM_BEHAVIOR_CATALOG.csv")
    rows = csv_rows(d / "COVERAGE_MATRIX.csv")
    expected = {r["behavior_id"] for r in catalog}
    actual = [r.get("behavior_id", "") for r in rows]
    for n in sorted(expected - set(actual)):
        err.append("missing behavior " + n)
    if len(actual) != len(set(actual)):
        err.append("duplicate behavior ids")
    for r in rows:
        rid = r.get("behavior_id", "?")
        t = r.get("technical_verdict", "")
        b = r.get("business_verdict", "")
        if t not in TECH:
            err.append(rid + ": invalid technical_verdict " + repr(t))
        if b not in BIZ:
            err.append(rid + ": invalid business_verdict " + repr(b))
        if t == "PASS" and not r.get("evidence_ref", "").strip():
            err.append(rid + ": PASS missing evidence_ref")
        if t == "FAIL" and not r.get("finding_id", "").strip():
            err.append(rid + ": FAIL missing finding_id")
        if t in {"BLOCKED", "NOT_COLLECTED", "NOT_PROVEN"} and not r.get("unresolved_reason", "").strip():
            err.append(rid + ": unresolved without reason")
        if b == "PASS" and t in {"BLOCKED", "NOT_COLLECTED", "NOT_PROVEN", "FAIL"}:
            err.append(rid + ": business PASS despite technical " + t)
    if (d / "SOURCE_FIELD_LEDGER.csv").exists():
        fr = csv_rows(d / "SOURCE_FIELD_LEDGER.csv")
        cols = {
            "source_field",
            "raw_provider_path",
            "approved_disposition",
            "approved_decision_source",
            "intended_odoo_target",
            "required_for_promotion",
        }
        if fr and not cols.issubset(fr[0]):
            err.append("SOURCE_FIELD_LEDGER missing required columns: " + ",".join(sorted(cols - set(fr[0]))))
        if len(fr) < 96:
            blocker_text = (d / "BLOCKERS.md").read_text(encoding="utf8") if (d / "BLOCKERS.md").is_file() else ""
            if "FIELD_INVENTORY_NOT_PROVEN" not in blocker_text:
                err.append(
                    f"SOURCE_FIELD_LEDGER has only {len(fr)} field rows; include FIELD_INVENTORY_NOT_PROVEN in BLOCKERS.md, or supply 96 source-bound field identities"
                )
            else:
                print(
                    f"WARNING: only {len(fr)} field identities; explicit FIELD_INVENTORY_NOT_PROVEN blocker preserved (no source-fidelity PASS)"
                )
        # Count alone is not semantic validity; never auto-pass.
    if (d / "PROVENANCE.json").exists():
        try:
            p = json.loads((d / "PROVENANCE.json").read_text(encoding="utf8"))
            if not (isinstance(p.get("git_sha"), str) and len(p["git_sha"]) == 40):
                err.append("PROVENANCE missing 40-char git_sha")
        except (ValueError, OSError) as ex:
            err.append("invalid PROVENANCE.json: " + str(ex))
    print(
        f"CRM evidence structural check: {len(expected)} frozen behaviors, {len(rows)} output rows, {len(err)} issue(s)"
    )
    for x in err:
        print(" - " + x)
    print("Note: even 0 issues does NOT establish source completeness, ORM execution or promotion acceptance.")
    return int(bool(err))


if __name__ == "__main__":
    raise SystemExit(main())

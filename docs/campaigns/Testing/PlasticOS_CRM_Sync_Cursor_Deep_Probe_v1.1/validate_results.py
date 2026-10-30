#!/usr/bin/env python3
"""Offline structure-only validator for a CRM Cursor evidence directory.

No network and no database writes. A clean result does not prove that tests
ran, that source census is complete, or that CRM promotion is earned.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

TECH = {"PASS", "FAIL", "BLOCKED", "NOT_COLLECTED", "NOT_PROVEN", "NOT_APPLICABLE"}
BIZ = {"PASS", "FAIL", "NOT_PROVEN", "DEFERRED_APPROVED", "NOT_APPLICABLE"}
DISPOSITIONS = {"native", "evidence", "material", "excluded", "pending"}
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
LEDGER_COLS = {
    "source_field",
    "raw_provider_path",
    "approved_disposition",
    "approved_decision_source",
    "intended_odoo_target",
    "required_for_promotion",
}
PROVENANCE_KEYS = (
    "git_sha",
    "source_digest",
    "image_before",
    "image_after",
    "template_before",
    "template_after",
    "postgres_identity",
    "enterprise_revision",
)
SHAREABLE = NEEDED
DIAGNOSTIC = re.compile(r"DIAGNOSTIC=(COMPLETE|PARTIAL|BLOCKED)\b")
PROMOTION = re.compile(r"CRM_PROMOTION=(PASS|FAIL|NOT_PROVEN)\b")
FINDING_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,}$")
PLACEHOLDER = re.compile(r"^(field|placeholder|todo|tbd|unnamed)([_ -]?\d+)?$", re.IGNORECASE)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRET = re.compile(r"(password\s*=|api_key\s*=|Authorization\s*:)", re.IGNORECASE)
PATH_SUFFIXES = {".json", ".log", ".md", ".csv", ".txt", ".py"}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def lanes(row: dict[str, str], catalog_row: dict[str, str]) -> set[str]:
    raw = row.get("evidence_lanes") or catalog_row.get("evidence_lanes") or ""
    return {part.strip() for part in raw.split("+") if part.strip()}


def priority(row: dict[str, str], catalog_row: dict[str, str]) -> str:
    if catalog_row.get("priority"):
        return catalog_row["priority"].strip()
    return (row.get("priority") or "").strip()


def path_tokens(ref: str) -> list[str]:
    tokens = []
    for part in re.split(r"[\s;]+", ref.strip()):
        part = part.strip().strip(",")
        if not part:
            continue
        suffix = Path(part).suffix.lower()
        if "/" in part or suffix in PATH_SUFFIXES:
            tokens.append(part)
    return tokens


def resolve_token(evidence: Path, token: str) -> bool:
    candidate = Path(token)
    if candidate.is_absolute():
        return candidate.is_file()
    return (evidence / token).is_file()


def git_toplevel(start: Path) -> tuple[Path | None, str]:
    """Worktree root of *start*, including a detached worktree.

    ``git rev-parse --show-toplevel`` follows the checkout that contains
    *start*. A linked worktree returns its own root, not the main checkout.
    """
    listed = subprocess.run(  # noqa: S603
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if listed.returncode != 0:
        detail = (listed.stderr or listed.stdout or "git rev-parse --show-toplevel failed").strip()
        return None, detail
    text = listed.stdout.strip()
    if not text:
        return None, "git rev-parse --show-toplevel returned an empty path"
    return Path(text).resolve(), ""


def repo_root(pack: Path) -> Path | None:
    found, _detail = git_toplevel(pack)
    return found


def evidence_location_errors(evidence: Path, pack: Path) -> list[str]:
    found, detail = git_toplevel(pack)
    if found is None:
        return ["cannot resolve the Git worktree that contains the pack: " + detail]
    root = (found / "docs" / "reports" / "evidence").resolve()
    if not root.is_dir():
        return ["this worktree has no docs/reports/evidence directory: " + root.as_posix()]
    resolved = evidence.resolve()
    try:
        resolved.relative_to(found)
    except ValueError:
        return ["evidence directory is not inside the Git worktree " + found.as_posix()]
    if resolved.parent != root:
        return ["evidence directory must be a campaign folder directly inside docs/reports/evidence"]
    return []


def untracked_evidence_files(evidence: Path, pack: Path) -> list[str]:
    repo = repo_root(pack)
    if repo is None:
        return ["cannot resolve the Git worktree for evidence tracking"]
    relative = evidence.resolve().relative_to(repo.resolve()).as_posix()
    listed = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), "ls-files", "-z", "--", relative],  # noqa: S607
        check=False,
        capture_output=True,
    )
    if listed.returncode != 0:
        return ["git ls-files failed for " + relative]
    tracked = {item.decode() for item in listed.stdout.split(b"\0") if item}
    missing = []
    for path in evidence.rglob("*"):
        if not path.is_file() or path.name == ".DS_Store":
            continue
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
        if rel not in tracked:
            missing.append("untracked evidence file " + rel)
    return missing


def main() -> int:  # noqa: C901
    if len(sys.argv) != 2:
        print("usage: python3 validate_results.py <evidence-directory>", file=sys.stderr)
        return 2
    evidence = Path(sys.argv[1])
    pack = Path(__file__).resolve().parent
    errors: list[str] = []
    errors.extend(evidence_location_errors(evidence, pack))
    for name in NEEDED:
        if not (evidence / name).is_file():
            errors.append("missing " + name)
    receipts = evidence / "TEST_EXECUTION_RECEIPTS"
    if not receipts.is_dir():
        errors.append("missing TEST_EXECUTION_RECEIPTS/")
    if not (evidence / "COVERAGE_MATRIX.csv").is_file():
        print("\n".join(errors))
        return 1

    catalog = csv_rows(pack / "CRM_BEHAVIOR_CATALOG.csv")
    catalog_by_id = {row["behavior_id"]: row for row in catalog}
    rows = csv_rows(evidence / "COVERAGE_MATRIX.csv")
    expected = set(catalog_by_id)
    actual = [row.get("behavior_id", "") for row in rows]
    for name in sorted(expected - set(actual)):
        errors.append("missing behavior " + name)
    if len(actual) != len(set(actual)):
        errors.append("duplicate behavior ids")

    findings = ""
    findings_path = evidence / "ROOT_CAUSE_FINDINGS.md"
    if findings_path.is_file():
        findings = findings_path.read_text(encoding="utf-8")
    blockers = ""
    blockers_path = evidence / "BLOCKERS.md"
    if blockers_path.is_file():
        blockers = blockers_path.read_text(encoding="utf-8")
    summary = ""
    summary_path = evidence / "SESSION_SUMMARY.md"
    if summary_path.is_file():
        summary = summary_path.read_text(encoding="utf-8")
        diagnostics = DIAGNOSTIC.findall(summary)
        promotions = PROMOTION.findall(summary)
        if re.search(r"DIAGNOSTIC=(COMPLETE|PARTIAL|BLOCKED)\|", summary):
            errors.append("SESSION_SUMMARY.md pastes the DIAGNOSTIC alternation; record one value")
        if re.search(r"CRM_PROMOTION=(PASS|FAIL|NOT_PROVEN)\|", summary):
            errors.append("SESSION_SUMMARY.md pastes the CRM_PROMOTION alternation; record one value")
        if len(diagnostics) != 1:
            errors.append(f"SESSION_SUMMARY.md must contain exactly one DIAGNOSTIC= verdict (found {len(diagnostics)})")
        if len(promotions) != 1:
            errors.append(
                f"SESSION_SUMMARY.md must contain exactly one CRM_PROMOTION= verdict (found {len(promotions)})"
            )
    else:
        diagnostics, promotions = [], []

    enterprise_pass = False
    src01_pass = False
    for row in rows:
        behavior_id = row.get("behavior_id", "?")
        technical = row.get("technical_verdict", "")
        business = row.get("business_verdict", "")
        catalog_row = catalog_by_id.get(behavior_id, {})
        if technical not in TECH:
            errors.append(behavior_id + ": invalid technical_verdict " + repr(technical))
        if business not in BIZ:
            errors.append(behavior_id + ": invalid business_verdict " + repr(business))
        if technical == "PASS" and not row.get("evidence_ref", "").strip():
            errors.append(behavior_id + ": PASS missing evidence_ref")
        if technical == "FAIL":
            finding_id = row.get("finding_id", "").strip()
            if not FINDING_ID.match(finding_id):
                errors.append(behavior_id + ": FAIL finding_id must match [A-Za-z][A-Za-z0-9_.-]{2,}")
            elif finding_id not in findings:
                errors.append(behavior_id + ": FAIL finding_id absent from ROOT_CAUSE_FINDINGS.md")
        if technical in {"BLOCKED", "NOT_COLLECTED", "NOT_PROVEN"} and not row.get("unresolved_reason", "").strip():
            errors.append(behavior_id + ": unresolved without reason")
        if business == "PASS" and technical in {"BLOCKED", "NOT_COLLECTED", "NOT_PROVEN", "FAIL"}:
            errors.append(behavior_id + ": business PASS despite technical " + technical)
        row_lanes = lanes(row, catalog_row)
        if technical == "PASS" and row_lanes & {"enterprise", "clone"}:
            enterprise_pass = True
            tokens = path_tokens(row.get("evidence_ref", ""))
            if not any(resolve_token(evidence, token) for token in tokens):
                errors.append(
                    behavior_id + ": enterprise/clone PASS evidence_ref names no file in the evidence directory"
                )
        if behavior_id == "SRC-01" and technical == "PASS":
            src01_pass = True
        if promotions == ["PASS"] and priority(row, catalog_row) == "GATE":
            if technical != "PASS" or business != "PASS":
                errors.append(behavior_id + ": GATE row blocks CRM_PROMOTION=PASS")

    if promotions == ["PASS"] and (
        "FIELD_INVENTORY_NOT_PROVEN" in blockers or "EXTERNAL_SOURCE_CENSUS_BLOCKED" in blockers
    ):
        errors.append("CRM_PROMOTION=PASS conflicts with a census or field-inventory blocker")

    if enterprise_pass and receipts.is_dir():
        native = list(receipts.rglob("*.test-receipt.json")) + list(receipts.rglob("*.test.log"))
        if not native:
            errors.append("enterprise/clone PASS without a native receipt or log in TEST_EXECUTION_RECEIPTS/")

    ledger_path = evidence / "SOURCE_FIELD_LEDGER.csv"
    if ledger_path.is_file():
        ledger_header = header(ledger_path)
        ledger = csv_rows(ledger_path) if ledger_header else []
        if ledger_header and not LEDGER_COLS.issubset(ledger_header):
            missing = ", ".join(sorted(LEDGER_COLS - set(ledger_header)))
            errors.append("SOURCE_FIELD_LEDGER missing required columns: " + missing)
        seen_fields: set[tuple[str, str]] = set()
        for index, field in enumerate(ledger, start=2):
            source_field = (field.get("source_field") or "").strip()
            provider_path = (field.get("raw_provider_path") or "").strip()
            disposition = (field.get("approved_disposition") or "").strip()
            decision = (field.get("approved_decision_source") or "").strip()
            if not source_field or not provider_path or not decision:
                errors.append(
                    f"SOURCE_FIELD_LEDGER row {index}: source_field, raw_provider_path, and approved_decision_source are required"
                )
            if source_field and PLACEHOLDER.match(source_field):
                errors.append(f"SOURCE_FIELD_LEDGER row {index}: placeholder source_field {source_field!r}")
            if disposition not in DISPOSITIONS:
                errors.append(f"SOURCE_FIELD_LEDGER row {index}: invalid approved_disposition {disposition!r}")
            key = (source_field, provider_path)
            if key in seen_fields:
                errors.append(f"SOURCE_FIELD_LEDGER duplicate field identity {source_field!r} {provider_path!r}")
            seen_fields.add(key)
        if len(ledger) < 96 and "FIELD_INVENTORY_NOT_PROVEN" not in blockers:
            errors.append(
                f"SOURCE_FIELD_LEDGER has only {len(ledger)} field rows; include FIELD_INVENTORY_NOT_PROVEN in BLOCKERS.md, or supply 96 source-bound field identities"
            )
        elif len(ledger) < 96:
            print(
                f"WARNING: only {len(ledger)} field identities; explicit FIELD_INVENTORY_NOT_PROVEN blocker preserved (no source-fidelity PASS)"
            )

    census_path = evidence / "SOURCE_CONTACT_CENSUS.csv"
    if census_path.is_file():
        census_header = header(census_path)
        template_header = header(pack / "SOURCE_CONTACT_CENSUS_TEMPLATE.csv")
        census_text = census_path.read_text(encoding="utf-8")
        if census_text.strip() and not set(template_header).issubset(census_header):
            missing = ", ".join(sorted(set(template_header) - set(census_header)))
            errors.append("SOURCE_CONTACT_CENSUS missing required columns: " + missing)
        census = csv_rows(census_path) if census_header else []
        if src01_pass and not census:
            errors.append("SRC-01 PASS requires at least one SOURCE_CONTACT_CENSUS data row")
        if not census and "EXTERNAL_SOURCE_CENSUS_BLOCKED" not in blockers:
            errors.append("empty SOURCE_CONTACT_CENSUS requires EXTERNAL_SOURCE_CENSUS_BLOCKED in BLOCKERS.md")
        for index, contact in enumerate(census, start=2):
            token = (contact.get("record_token") or "").strip()
            if not token or token.isdigit() or "@" in token:
                errors.append(f"SOURCE_CONTACT_CENSUS row {index}: record_token must be a non-numeric token without @")

    provenance_path = evidence / "PROVENANCE.json"
    if provenance_path.is_file():
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            errors.append("invalid PROVENANCE.json: " + str(exc))
            provenance = {}
        if not isinstance(provenance, dict):
            errors.append("PROVENANCE.json must be an object")
            provenance = {}
        git_sha = provenance.get("git_sha")
        if not (isinstance(git_sha, str) and re.fullmatch(r"[0-9a-f]{40}", git_sha)):
            errors.append("PROVENANCE git_sha must be 40 lowercase hex characters")
        for key in PROVENANCE_KEYS:
            if key == "git_sha":
                continue
            value = provenance.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append("PROVENANCE missing " + key)

    for name in SHAREABLE:
        path = evidence / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if EMAIL.search(text):
            errors.append(name + ": shareable file contains an email address")
    if evidence.is_dir() and not evidence_location_errors(evidence, pack):
        errors.extend(untracked_evidence_files(evidence, pack))
        for path in evidence.rglob("*"):
            if not path.is_file() or path.name == ".DS_Store":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if SECRET.search(text):
                errors.append(path.name + ": tracked evidence contains a secret marker")

    print(
        f"CRM evidence structural check: {len(expected)} frozen behaviors, {len(rows)} output rows, {len(errors)} issue(s)"
    )
    for item in errors:
        print(" - " + item)
    print("Note: even 0 issues does NOT establish source completeness, ORM execution or promotion acceptance.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())

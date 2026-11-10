#!/usr/bin/env python3
"""Read-only validation of one frozen ERP worksheet-image cohort.

Inputs are operator-exported CSVs, NOT authoritative proof of live Production state.
No SQL, Odoo API, database writes, or private file upload is performed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

JOURNAL = (
    "ImageID",
    "DocID",
    "RefID",
    "RefType",
    "FileExt",
    "BlobSize",
    "RawBytes",
    "RawSha256",
    "DecodedBytes",
    "DecodedSha256",
    "Status",
    "ImportScope",
)
TRANSACTIONS = ("id", "name", "company_id")
IMPORTS = ("ImageID", "odoo_document_id", "odoo_transaction_id", "status", "decoded_sha256")
HEX = re.compile(r"[0-9a-fA-F]{64}\Z")
VALID_TYPES = {"W", "#", "P", "E", "B"}


def read_csv(path: Path, required: tuple[str, ...]) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"missing CSV header: {path.name}")
        missing = set(required) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"missing columns in {path.name}: {sorted(missing)}")
        return list(reader)


def decimal_int(value: str) -> int:
    # The historical PowerShell extractor can emit decimal-looking SQL float text.
    v = str(value or "")
    if not re.fullmatch(r"[0-9]+(?:\.0+)?", v):
        raise ValueError("not a nonnegative integral size")
    return int(v.split(".")[0])


def canonical_ext(value: str) -> str:
    ext = (value or "").strip().lstrip(".")
    return ext if 1 <= len(ext) <= 8 and ext.isascii() and ext.isalnum() else "bin"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def analyze(
    journal_path: Path,
    transaction_path: Path,
    import_path: Path | None = None,
    decoded_dir: Path | None = None,
    raw_dir: Path | None = None,
) -> dict:
    journal = read_csv(journal_path, JOURNAL)
    transactions = read_csv(transaction_path, TRANSACTIONS)
    imports = read_csv(import_path, IMPORTS) if import_path else []
    problems: list[str] = []
    if not journal:
        problems.append("source journal is empty; cohort completeness cannot pass")
    if not transactions:
        problems.append("transaction census is empty; verify actual complete Production export")
    counted = Counter()
    tx_by_name: dict[str, list[dict]] = defaultdict(list)
    ids_seen = set()
    for row in transactions:
        if not row["id"] or not row["name"] or not row["company_id"]:
            problems.append("transaction census has an empty id/name/company_id")
        if row["id"] in ids_seen:
            problems.append("duplicate transaction record ID in census")
        ids_seen.add(row["id"])
        # EXACT match: no stripping/case folding/shortening/suffix removal.
        tx_by_name[row["name"]].append(row)

    import_by_image: dict[str, dict] = {}
    used_doc_ids: set[str] = set()
    for row in imports:
        image_id = row["ImageID"]
        if image_id in import_by_image:
            problems.append(f"duplicate import-ledger image ID: {image_id}")
        import_by_image[image_id] = row
        if row["status"] not in ("imported", "failed"):
            problems.append(f"unknown import status for {image_id}")
        if row["status"] == "imported":
            doc_id = row["odoo_document_id"]
            if not doc_id or doc_id in used_doc_ids:
                problems.append(f"absent or reused native document ID for {image_id}")
            used_doc_ids.add(doc_id)
            if not HEX.fullmatch(row["decoded_sha256"]):
                problems.append(f"missing/invalid import digest for {image_id}")
        elif row["status"] == "failed" and not row.get("reason", "").strip():
            problems.append(f"failed ledger row missing reason for {image_id}")

    image_seen: set[str] = set()
    eligible_seen: set[str] = set()
    match_by_image: dict[str, str] = {}
    examples: dict[str, list[str]] = defaultdict(list)
    for row in journal:
        image_id = row["ImageID"]
        if not image_id or image_id in image_seen:
            problems.append(f"empty/duplicate source ImageID: {image_id}")
            continue
        image_seen.add(image_id)
        kind = row["RefType"]
        if kind not in VALID_TYPES:
            problems.append(f"unknown source RefType for ImageID {image_id}")
            continue
        counted["source_total"] += 1
        if kind not in ("W", "#"):
            counted[f"archive_only_{kind}"] += 1
            if image_id in import_by_image:
                problems.append(f"excluded RefType imported/attempted for ImageID {image_id}")
            continue
        counted["eligible"] += 1
        counted[f"eligible_{kind}"] += 1
        eligible_seen.add(image_id)
        expected_scope = "eligible"
        if row["ImportScope"] != expected_scope:
            problems.append(f"wrong ImportScope for eligible ImageID {image_id}")

        defect = None
        try:
            size = decimal_int(row["BlobSize"])
            decoded = decimal_int(row["DecodedBytes"])
            if size != decoded or size <= 0:
                defect = "decoded-size-mismatch"
        except ValueError:
            defect = "invalid-size"
        if row["Status"] != "ok":
            defect = "extract-status-" + (row["Status"] or "empty")
        if not HEX.fullmatch(row["RawSha256"]) or not HEX.fullmatch(row["DecodedSha256"]):
            defect = "missing-invalid-source-hash"
        if raw_dir is not None:
            raw_path = raw_dir / (image_id + ".bin")
            try:
                raw_expected = decimal_int(row["RawBytes"])
                if raw_path.stat().st_size != raw_expected or sha256_file(raw_path) != row["RawSha256"].lower():
                    defect = "compressed-source-hash-or-size-mismatch"
            except (OSError, ValueError):
                defect = "compressed-source-unavailable-or-invalid"
        if decoded_dir is not None and defect is None:
            file_path = decoded_dir / (image_id + "." + canonical_ext(row["FileExt"]))
            try:
                if file_path.stat().st_size != size or sha256_file(file_path) != row["DecodedSha256"].lower():
                    defect = "extracted-file-hash-or-size-mismatch"
            except OSError:
                defect = "extracted-file-unavailable"

        if defect:
            bucket = "integrity_failure"
            examples[bucket].append(image_id + ":" + defect)
        else:
            matches = tx_by_name.get(row["RefID"], [])
            if len(matches) == 0:
                bucket = "missing_transaction"
            elif len(matches) > 1:
                bucket = "ambiguous_transaction"
            else:
                bucket = "unique_match"
                match_by_image[image_id] = matches[0]["id"]
            if bucket != "unique_match":
                examples[bucket].append(image_id + ":" + row["RefID"])
        counted[bucket] += 1

        result = import_by_image.get(image_id)
        if bucket != "unique_match":
            if result:
                problems.append(f"import ledger writes or attempts non-unique/integrity source ImageID {image_id}")
            continue
        if not result:
            counted["not_attempted"] += 1
            continue
        if result["status"] == "failed":
            counted["import_failure"] += 1
            examples["import_failure"].append(image_id + ":" + result.get("reason", ""))
            continue
        if (
            result["odoo_transaction_id"] != match_by_image[image_id]
            or result["decoded_sha256"].lower() != row["DecodedSha256"].lower()
        ):
            problems.append(f"imported record or digest mismatches source/crosswalk ImageID {image_id}")
        counted["successfully_imported"] += 1

    if set(import_by_image) - eligible_seen:
        problems.append("import ledger includes unknown or noneligible ImageIDs")
    if counted["eligible"] != sum(
        counted[x] for x in ("unique_match", "missing_transaction", "ambiguous_transaction", "integrity_failure")
    ):
        problems.append("source eligibility identity did not close")
    if counted["unique_match"] != sum(counted[x] for x in ("successfully_imported", "import_failure", "not_attempted")):
        problems.append("unique match import identity did not close")

    return {
        "schema": "plasticos.worksheet-image-readonly-reconciliation/v1",
        "evidence_class": "READ_ONLY_OPERATOR_EXPORTED_DATA_NOT_HOSTED_RUNTIME_PROOF",
        "journal_sha256": sha256_file(journal_path),
        "transactions_csv_sha256": sha256_file(transaction_path),
        "imports_csv_sha256": sha256_file(import_path) if import_path else None,
        "decoded_originals_verification": "ALL_ELIGIBLE_INTACT_FILES_CHECKED" if decoded_dir else "NOT_RUN",
        "raw_originals_verification": "ALL_ELIGIBLE_RAW_FILES_CHECKED" if raw_dir else "NOT_RUN",
        "counts": dict(sorted(counted.items())),
        "problems": problems,
        "examples_first_ten_each": {k: v[:10] for k, v in sorted(examples.items())},
        "verdict": "STRUCTURAL_FAIL" if problems else "STRUCTURAL_PASS_NOT_PRODUCTION_ATTESTATION",
        "required_live_proofs": [
            "complete and company-authorized Production transaction census",
            "observed Production build and installed native Documents module",
            "restored and opened native Odoo.sh DB+filestore backup",
            "source journal and original bytes reverified at frozen source epoch",
            "native Documents ORM import-readback and zero-side-effect receipt",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--journal", type=Path, required=True, help="Private extractor journal.csv")
    ap.add_argument(
        "--transactions",
        type=Path,
        required=True,
        help="Complete authorized Odoo transaction export; id,name,company_id",
    )
    ap.add_argument(
        "--imports",
        type=Path,
        help="Importer receipt CSV (ImageID,odoo_document_id,odoo_transaction_id,status,decoded_sha256,reason)",
    )
    ap.add_argument(
        "--decoded-dir", type=Path, help="Private decoded originals, files named <ImageID>.<source extension>"
    )
    ap.add_argument("--raw-dir", type=Path, help="Private raw compressed originals, files named <ImageID>.bin")
    ap.add_argument("--output", type=Path, help="Private JSON receipt destination")
    ap.add_argument(
        "--expect-source-count", type=int, help="Exact independently confirmed full manifest count for this epoch"
    )
    ap.add_argument("--expect-eligible-count", type=int, help="Exact independently confirmed W/# count for this epoch")
    ap.add_argument(
        "--require-complete-import",
        action="store_true",
        help="Fail if any unique match was not imported successfully; requires --imports and --decoded-dir",
    )
    args = ap.parse_args()
    try:
        result = analyze(args.journal, args.transactions, args.imports, args.decoded_dir, args.raw_dir)
    except (OSError, ValueError, csv.Error) as exc:
        print(json.dumps({"verdict": "INPUT_INVALID", "error": str(exc)}, indent=2))
        return 2
    if args.expect_source_count is not None and result["counts"].get("source_total", 0) != args.expect_source_count:
        result["problems"].append("source manifest row count differs from supplied independent manifest census")
    if args.expect_eligible_count is not None and result["counts"].get("eligible", 0) != args.expect_eligible_count:
        result["problems"].append("eligible count differs from supplied independent source census")
    if args.require_complete_import:
        if args.imports is None or args.decoded_dir is None or args.raw_dir is None:
            result["problems"].append("complete import check requires --imports, --decoded-dir and --raw-dir")
        if result["counts"].get("not_attempted", 0) or result["counts"].get("import_failure", 0):
            result["problems"].append("some unique-match images remain not attempted or failed")
    if result["problems"]:
        result["verdict"] = "STRUCTURAL_FAIL"
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

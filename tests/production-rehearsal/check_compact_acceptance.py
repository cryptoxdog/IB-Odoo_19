#!/usr/bin/env python3
"""Prove the compact Gate 6 receipts against the retained full snapshots.

Reads ``evidence/2026-11-08_124519`` and re-reads ``odoo_test_cutover``.
Does not start an import and is not part of ``pytest tests/``. Exits 2 when
the clone or the retained snapshots are absent. The retained snapshots stay
where they are; the publish checks use a temporary evidence directory.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[1]
RETAINED = KIT / "evidence" / "2026-11-08_124519"
FULL_NAMES = (
    "05-erp-fidelity.json",
    "05-erp-fidelity-odoo.json",
    "05-erp-summary-census.json",
)
CLONE = "odoo_test_cutover"


def _load_common():
    spec = importlib.util.spec_from_file_location("rehearsal_compact_common", KIT / "common.py")
    if spec is None or spec.loader is None:
        raise SystemExit(2)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        _fail(f"retained snapshot absent: {path.name}", 2)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        _fail(f"retained snapshot is not an object: {path.name}", 2)
    return loaded


def _clone_count(sql: str) -> int:
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(ROOT / "docker-compose.yml"),
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "odoo",
            "-d",
            CLONE,
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=ROOT,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip().isdigit():
        _fail(f"{CLONE} is not readable", 2)
    return int(completed.stdout.strip())


def _price_basis(rows: list) -> list[dict]:
    found = []
    for row in rows:
        if not isinstance(row, dict) or row.get("result") != "FAIL":
            continue
        if row.get("source_field") != "PriceBasis" or row.get("actual") != "FOB":
            continue
        if str(row.get("source_value") or "").strip():
            continue
        found.append(row)
    return found


def _assert_publish(common, census_receipt: dict, fidelity_receipt: dict) -> None:
    evidence = Path(tempfile.mkdtemp(prefix="gate6-evidence-"))
    staging = Path(tempfile.mkdtemp(prefix="gate6-staging-"))
    common.publish_json(evidence / "05-erp-summary-census.json", census_receipt, staging_dir=staging)
    common.publish_json(evidence / "05-erp-fidelity.json", fidelity_receipt, staging_dir=staging)
    published_census = json.loads((evidence / "05-erp-summary-census.json").read_text(encoding="utf-8"))
    published_fidelity = json.loads((evidence / "05-erp-fidelity.json").read_text(encoding="utf-8"))
    if "anomalies" in published_census or "unresolved" in published_census:
        _fail("completed publish left an anomaly or unresolved array in the evidence directory")
    if (evidence / "05-erp-fidelity-odoo.json").exists():
        _fail("completed publish wrote the clone snapshot into the evidence directory")
    if (evidence / "05-erp-fidelity.json").stat().st_size > 1000 * 1024:
        _fail("compact fidelity receipt exceeds 1000KB")
    if any(row.get("result") != "FAIL" for row in published_fidelity.get("rows") or []):
        _fail("compact fidelity receipt stored a row that is not a mismatch")
    real_replace = os.replace

    def _interrupted(*_args, **_kwargs):
        raise OSError(0, "interrupted before rename")

    os.replace = _interrupted
    try:
        try:
            common.publish_json(evidence / "05-erp-fidelity-odoo.json", {"evidence": "complete"}, staging_dir=staging)
        except OSError:
            pass
        else:
            _fail("interrupted publish completed the rename")
    finally:
        os.replace = real_replace
    if (evidence / "05-erp-fidelity-odoo.json").exists():
        _fail("interrupted publish left the clone snapshot in the evidence directory")
    if any("anomalies" in path.read_text(encoding="utf-8") for path in evidence.glob("*census.json")):
        _fail("interrupted publish left an anomaly array in the evidence directory")


def main() -> int:
    if not RETAINED.is_dir():
        _fail(f"retained evidence absent: {RETAINED.name}", 2)
    for name in FULL_NAMES:
        if not (RETAINED / name).is_file():
            _fail(f"retained snapshot absent: {name}", 2)
    common = _load_common()
    census = _read_json(RETAINED / "05-erp-summary-census.json")
    fidelity = _read_json(RETAINED / "05-erp-fidelity.json")
    snapshot = _read_json(RETAINED / "05-erp-fidelity-odoo.json")
    receipt = common.compact_census(census)
    unresolved = census.get("unresolved") if isinstance(census.get("unresolved"), list) else []
    anomalies = census.get("anomalies") if isinstance(census.get("anomalies"), list) else []
    if receipt["unresolved_count"] != len(unresolved):
        _fail("compact unresolved count does not match the retained census")
    if receipt["attributed_count"] + receipt["unattributed_count"] != receipt["unresolved_count"]:
        _fail("compact attribution counts do not partition the unresolved rows")
    if sum(receipt["anomaly_counts"].values()) != len(anomalies):
        _fail("compact anomaly counts do not match the retained census")
    origin = str(census.get("source_origin") or "")
    if receipt["origin_sha256"] != hashlib.sha256(origin.encode()).hexdigest() or not receipt["origin_sha256"]:
        _fail("compact origin digest does not match the retained census")
    rows = fidelity.get("rows") if isinstance(fidelity.get("rows"), list) else []
    mismatches = [row for row in rows if isinstance(row, dict) and row.get("result") == "FAIL"]
    if len(mismatches) != fidelity.get("failed"):
        _fail("retained FAIL rows do not equal the failed count")
    basis = _price_basis(mismatches)
    if len(basis) != 5:
        _fail(f"expected five empty PriceBasis values stored as FOB, found {len(basis)}")
    compact = dict(fidelity)
    compact["rows"] = mismatches
    compact["rows_retained"] = "failures"
    if compact["compared"] != fidelity["compared"] or compact["failed"] != fidelity["failed"]:
        _fail("compact counters do not match the retained comparison")
    # The retained full dump predates the persisted coverage matrix. The compact
    # receipt carries the current matrix; the counters and the mismatches stay the retained ones.
    if not isinstance(compact.get("coverage"), list):
        fidelity_mod = importlib.util.spec_from_file_location("rehearsal_fidelity_contract", KIT / "fidelity.py")
        if fidelity_mod is None or fidelity_mod.loader is None:
            _fail("fidelity contract could not be loaded", 2)
        module = importlib.util.module_from_spec(fidelity_mod)
        fidelity_mod.loader.exec_module(module)
        compact["coverage"] = module.COVERAGE
    if not compact.get("source_fingerprint"):
        compact["source_fingerprint"] = hashlib.sha256(
            f"{compact['compared']}:{compact['failed']}:{compact['rejected']}:{compact['unmapped']}".encode()
        ).hexdigest()
    if not any(isinstance(row, dict) and row.get("source_field") == "CompanyNm" for row in compact["coverage"]):
        _fail("compact coverage does not name a mapped company field")
    previous = common.fidelity_failures(fidelity)
    current = common.fidelity_failures(compact)
    if not previous or not current or previous[0][0] != "erp-fidelity-discrepancy" or current[0][0] != previous[0][0]:
        _fail("compact receipt does not reproduce the retained gate verdict")
    if not all(row in compact["rows"] for row in basis):
        _fail("the five PriceBasis mismatches are not in the compact receipt")
    partners = [
        row
        for row in snapshot.get("partners") or []
        if isinstance(row, dict) and str(row.get("xmlid") or "").startswith("legacy_erp_cp_")
    ]
    clone_partners = _clone_count(
        "SELECT COUNT(*) FROM ir_model_data "
        "WHERE module = 'plasticos_transaction' AND model = 'res.partner' AND name LIKE 'legacy_erp_cp_%'"
    )
    if clone_partners != len(partners):
        _fail(f"{CLONE} holds {clone_partners} counterparties; the retained snapshot holds {len(partners)}")
    _assert_publish(common, receipt, compact)
    for name in FULL_NAMES:
        if not (RETAINED / name).is_file():
            _fail(f"acceptance removed a retained snapshot: {name}")
    print("compact acceptance passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

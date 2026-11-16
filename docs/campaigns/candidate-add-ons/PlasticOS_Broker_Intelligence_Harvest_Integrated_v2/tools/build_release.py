#!/usr/bin/env python3
"""Run portable gates, emit a fresh manifest, and verify a revised release ZIP.

This is not Odoo runtime acceptance. No other repositories are touched.
"""

import argparse
import hashlib
import io
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

sys.dont_write_bytecode = True
from validate_package import ADDONS, ROOT, validate  # noqa: E402

HARVEST_SHA256 = "2c0220acdc45c95ffe184da4e3b13dee58ec426a3b6d571aeae97bc02277062a"
BASELINE_PACK_SHA256 = "649389e7b3fe163067e68beff6fa48d6518d0fed27f9482b171468eac79fe183"
KERNEL_SHA256 = "dc6cbd25ffb3be5be681db984afeeda6e33d78929bb64854f23c6cb94a6ffab3"
PARENT_REVISED_PACK_SHA256 = "8175afa06619aadd2ad41ffb2bd0db0f30eea7d6920ded33f8cce99c137b3e66"
LEVERAGE_KERNEL_SHA256 = "f7fe111189a2884cff8ab77ebc7828d0e949bc90f4b569a8026a2f4a899bd75e"
ALIGNMENT_KERNEL_SHA256 = "ce9f7d2face6e7007c27313cbc885a5d11df85335877851e60ddb87b84adb639"
INPUT_LEVERAGE_REVISED_PACK_SHA256 = "972ddcc80169306a8dd3441687de59542539b9504c3ae26bf8c4d2a945f9d96f"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs():
    records = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name == "BUILD_MANIFEST.json":
            continue
        if path.is_symlink() or "__pycache__" in path.parts or path.suffix == ".pyc":
            raise ValueError(f"unsafe or cached file: {path}")
        content = path.read_bytes()
        records.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(content), "bytes": len(content)})
    return records


def offline_tests():
    cases = unittest.defaultTestLoader.discover(start_dir=str(ROOT / "tests_offline"))
    capture = io.StringIO()
    outcome = unittest.TextTestRunner(stream=capture, verbosity=1).run(cases)
    result = {
        "tests": outcome.testsRun,
        "failures": len(outcome.failures),
        "errors": len(outcome.errors),
        "skipped": len(outcome.skipped),
        "status": "PASS" if outcome.wasSuccessful() else "FAIL",
    }
    if not outcome.wasSuccessful():
        raise RuntimeError("Offline test suite failed:\n" + capture.getvalue())
    if not result["tests"]:
        raise RuntimeError("Offline suite discovered zero tests")
    return result


def build(archive):
    archive = Path(archive).resolve()
    if archive.is_relative_to(ROOT.resolve()):
        raise ValueError("ZIP output must be outside the source tree")
    pre = validate()
    if pre["errors"]:
        raise RuntimeError("Static source gates failed: " + ", ".join(pre["errors"]))
    observed = offline_tests()
    records = inputs()
    manifest = {
        "schema": "plasticos-broker-intelligence-build/v2",
        "status": "offline-source-validated-only",
        "created_utc": datetime.now(UTC).isoformat(),
        "repo": "cryptoxdog/IB-Odoo_19",
        "branch": "Staging",
        "staging_sha": "d25da3236887c924c8a0164b00c1198f1804a2ea",
        "unchanged_code_owner_since": "c2c72bc36d6201d4114531a8f666c411db612f64",
        "open_pr_numbers_at_alignment_inspection": [471],
        "open_pr_count_observed_at_original_inspection": 0,
        "source_zip_sha256": HARVEST_SHA256,
        "baseline_package_sha256": BASELINE_PACK_SHA256,
        "improvement_kernel_sha256": KERNEL_SHA256,
        "input_revised_pack_sha256": PARENT_REVISED_PACK_SHA256,
        "recursive_leverage_kernel_sha256": LEVERAGE_KERNEL_SHA256,
        "recursive_alignment_kernel_sha256": ALIGNMENT_KERNEL_SHA256,
        "input_leverage_revised_pack_sha256": INPUT_LEVERAGE_REVISED_PACK_SHA256,
        "standalone_v1_available": False,
        "addon_roots": ADDONS,
        "draft_knowledge_seed_records": pre["counts"].get("draft_candidates"),
        "offline_unittest_observed": observed,
        "odoo_enterprise_registry": "NOT_RUN",
        "files": records,
        "manifest_self_hash_excluded_to_avoid_recursion": True,
    }
    (ROOT / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    gated = validate(verify_manifest=True)
    if gated["errors"]:
        raise RuntimeError("Manifest integrity gates failed: " + ", ".join(gated["errors"]))
    all_paths = sorted([ROOT / x["path"] for x in records] + [ROOT / "BUILD_MANIFEST.json"])
    archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=8) as z:
        for file in all_paths:
            z.write(file, f"{ROOT.name}/{file.relative_to(ROOT).as_posix()}")
    expected = {f"{ROOT.name}/{item['path']}": item["sha256"] for item in records}
    with ZipFile(archive) as z:
        error = z.testzip()
        if error:
            raise RuntimeError(f"Archive CRC failure: {error}")
        names = z.namelist()
        if len(names) != len(set(names)) or len(names) != len(expected) + 1:
            raise RuntimeError("Archive member inventory mismatch")
        for addon in ADDONS:
            if f"{ROOT.name}/{addon}/__manifest__.py" not in names:
                raise RuntimeError(f"Addon manifest missing: {addon}")
        for name, checksum in expected.items():
            if name not in names or sha(z.read(name)) != checksum:
                raise RuntimeError(f"Archive member hash mismatch: {name}")
        if z.read(f"{ROOT.name}/BUILD_MANIFEST.json") != (ROOT / "BUILD_MANIFEST.json").read_bytes():
            raise RuntimeError("Archived manifest content mismatch")
    return {
        "artifact": str(archive),
        "sha256": sha(archive.read_bytes()),
        "archive_size_bytes": archive.stat().st_size,
        "member_files": len(all_paths),
        "source_files_verified": len(records),
        "crc": "PASS",
        "member_sha256": "PASS",
        "static": gated,
        "offline_unittest_observed": observed,
        "odoo_registry": "NOT_RUN",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run portable checks and package a revised Odoo addon candidate")
    parser.add_argument("--output", type=Path, default=ROOT.parent / f"{ROOT.name}_Revised.zip")
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2, sort_keys=True))

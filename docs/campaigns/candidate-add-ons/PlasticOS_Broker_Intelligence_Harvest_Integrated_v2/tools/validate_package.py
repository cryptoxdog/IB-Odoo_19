#!/usr/bin/env python3
"""Static, source-based Odoo addon packaging gates. No Odoo registry is emulated."""

import ast
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ADDONS = (
    "plasticos_broker_intelligence",
    "plasticos_broker_intelligence_mack",
    "plasticos_broker_intelligence_web_leads",
    "plasticos_broker_intelligence_rejections",
)
BANNED = bytes([99, 105, 101, 116, 114, 97, 100, 101])


def validate(*, verify_manifest=False):
    errors = []
    counts = Counter()
    manifest_data = {}
    models = set()
    for name in ADDONS:
        folder = ROOT / name
        if not (folder / "__init__.py").is_file():
            errors.append(f"{name}: missing package initializer")
            continue
        try:
            manifest = ast.literal_eval((folder / "__manifest__.py").read_text())
        except (ValueError, SyntaxError, OSError) as exc:
            errors.append(f"{name}: invalid Odoo manifest: {exc}")
            continue
        manifest_data[name] = manifest
        if manifest.get("auto_install") is not False or manifest.get("installable") is not True:
            errors.append(f"{name}: addon must be explicit and installable")
        if not str(manifest.get("version") or "").startswith("19.0."):
            errors.append(f"{name}: not an Odoo 19 addon version")
        if name != ADDONS[0] and ADDONS[0] not in manifest.get("depends", ()):
            errors.append(f"{name}: missing direct core dependency")
        for data_path in manifest.get("data", ()):
            if not (folder / data_path).is_file():
                errors.append(f"{name}: declared data file missing: {data_path}")
        counts["addons"] += 1

    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            errors.append(f"dependency cycle: {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dependency in manifest_data[node].get("depends", ()):
            if dependency in manifest_data:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for name in manifest_data:
        visit(name)

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            errors.append(f"symlink prohibited: {rel}")
        if path.name.endswith((".pyc", ".pyo", ".sqlite")) or "__pycache__" in path.parts:
            errors.append(f"build cache in package: {rel}")
            continue
        if any(x == ".env" or x.startswith(".env.") for x in path.parts):
            errors.append(f"environment file in package: {rel}")
        data = path.read_bytes()
        if BANNED in data.lower() or BANNED in rel.lower().encode():
            errors.append(f"prohibited legacy identifier: {rel}")
        if (b"-----BEGIN" + b" PRIVATE KEY-----") in data or (b"-----BEGIN OPENSSH" + b" PRIVATE KEY-----") in data:
            errors.append(f"private key in package: {rel}")
        if path.suffix == ".py":
            try:
                compile(data, rel, "exec", dont_inherit=True)
                counts["compiled_python_files"] += 1
            except SyntaxError as exc:
                errors.append(f"python compile failure: {rel}: {exc}")
            if "/models/" in rel or "/wizards/" in rel:
                models.update(re.findall(rb"_name\s*=\s*[\'\"]([a-z0-9_.]+)[\'\"]", data))
        elif path.suffix == ".xml":
            try:
                tree = ET.fromstring(data)
                if tree.tag != "odoo":
                    errors.append(f"{rel}: XML root is not odoo")
                xml_ids = [x.get("id") for x in tree.findall("record") if x.get("id")]
                xml_ids += [x.get("id") for x in tree.findall("menuitem") if x.get("id")]
                if len(xml_ids) != len(set(xml_ids)):
                    errors.append(f"{rel}: duplicate XML IDs")
                counts["parsed_xml_files"] += 1
            except ET.ParseError as exc:
                errors.append(f"XML parse failure: {rel}: {exc}")
        elif path.name == "ir.model.access.csv":
            try:
                rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
                cols = {"model_id:id", "group_id:id", "perm_read", "perm_write", "perm_create", "perm_unlink"}
                if not rows or cols - set(rows[0]):
                    errors.append(f"{rel}: incomplete Odoo ACL CSV")
                counts["acl_rows"] += len(rows)
            except (UnicodeError, csv.Error) as exc:
                errors.append(f"ACL read failure {rel}: {exc}")
        counts["packaged_files_without_manifest"] += 1

    # Every ACL model reference must come from a concrete model declared in an addon.
    actual_models = {b"model_" + m.replace(b".", b"_") for m in models}
    for csv_path in ROOT.rglob("ir.model.access.csv"):
        rows = list(csv.DictReader(csv_path.open()))
        for row in rows:
            encoded = row.get("model_id:id", "").encode()
            if encoded not in actual_models:
                errors.append(f"undefined ACL model: {csv_path.relative_to(ROOT)}:{encoded.decode()}")

    seeds = ROOT / ADDONS[0] / "data/knowledge_drafts.xml"
    if seeds.exists():
        seed_root = ET.parse(seeds).getroot()
        records = seed_root.findall("record")
        counts["draft_candidates"] = len(records)
        if len(records) != 106 or seed_root.get("noupdate") != "1":
            errors.append("expected exactly 106 replay-safe draft candidates")
        for item in records:
            cols = {x.get("name"): x.text or "" for x in item.findall("field")}
            if "state" in cols or "reviewer_id" in cols or "reviewed_at" in cols:
                errors.append("harvest candidate attempted auto-admission")
            if len(cols.get("source_sha256", "")) != 64:
                errors.append("harvest candidate has invalid source hash length")

    h = ROOT / "source_catalog/semantic_harvest_v1"
    if not (h / "FILE_MANIFEST.sha256").is_file():
        errors.append("harvest source hash manifest missing")
    else:
        for line in (h / "FILE_MANIFEST.sha256").read_text().splitlines():
            sha, path = line.split("  ", 1)
            destination = h / path
            if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != sha:
                errors.append(f"harvest file digest mismatch: {path}")
            else:
                counts["harvest_source_files_verified"] += 1

    if verify_manifest:
        path = ROOT / "BUILD_MANIFEST.json"
        if not path.is_file():
            errors.append("BUILD_MANIFEST.json missing")
        else:
            final = json.loads(path.read_text())
            expected = {x["path"]: x for x in final.get("files", ())}
            observed = {
                p.relative_to(ROOT).as_posix(): p
                for p in ROOT.rglob("*")
                if p.is_file() and p.name != "BUILD_MANIFEST.json" and "__pycache__" not in p.parts
            }
            if expected.keys() != observed.keys():
                errors.append("build manifest file inventory mismatch")
            for rel, p in observed.items():
                if rel in expected and (
                    hashlib.sha256(p.read_bytes()).hexdigest() != expected[rel]["sha256"]
                    or p.stat().st_size != expected[rel]["bytes"]
                ):
                    errors.append(f"manifest digest mismatch: {rel}")
            counts["manifest_files_verified"] = len(observed)
    return {
        "status": "PASS" if not errors else "FAIL",
        "counts": dict(counts),
        "errors": errors,
        "staging_sha": "d25da3236887c924c8a0164b00c1198f1804a2ea",
        "scope": "static source checks only; does not execute Odoo registry or ORM",
    }


if __name__ == "__main__":
    checks = validate(verify_manifest="--verify-manifest" in sys.argv)
    print(json.dumps(checks, sort_keys=True, indent=2))
    sys.exit(bool(checks["errors"]))

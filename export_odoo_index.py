#!/usr/bin/env python3
"""
Odoo 19 Repo Index — machine-built inventory for:
- Model names, XML external IDs, seed records
- Views/security/actions, migrations/tests
- Namespace drift, dependency DAG, compliance scan
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = REPO_ROOT / "reports" / "repo-index"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. Full Model Index (Python / ORM registry map)
# ---------------------------------------------------------------------------

def _parse_manifest(manifest_path: Path) -> dict | None:
    """Parse __manifest__.py and return dict."""
    try:
        content = manifest_path.read_text(encoding="utf-8")
        # Extract dict from manifest (handles multiline)
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None
        return ast.literal_eval(match.group(0))
    except (SyntaxError, ValueError):
        return None


def _extract_model_attrs(content: str) -> dict:
    """Extract _name, _inherit, _description, fields, compute, constraints from model file."""
    attrs: dict = {
        "_name": None,
        "_inherit": None,
        "_description": None,
        "fields": [],
        "compute_methods": [],
        "api_constrains": [],
        "_sql_constraints": [],
        "models_constraint": [],
        "class_name": None,
        "namespace_drift": None,
    }
    # Class name (Plastos vs plasticos drift)
    class_match = re.search(r"class\s+(\w+)\s*\([^)]*models\.Model", content)
    if class_match:
        attrs["class_name"] = class_match.group(1)
    # _name
    m = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
    if m:
        attrs["_name"] = m.group(1)
    # _inherit (string or list)
    m = re.search(r'_inherit\s*=\s*\[([^\]]+)\]', content)
    if m:
        attrs["_inherit"] = [x.strip().strip('"\'') for x in m.group(1).split(",")]
    else:
        m = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            attrs["_inherit"] = [m.group(1)]
    # _description
    m = re.search(r'_description\s*=\s*["\']([^"\']*)["\']', content)
    if m:
        attrs["_description"] = m.group(1)
    # Fields
    for m in re.finditer(r"(\w+)\s*=\s*fields\.(\w+)\s*\(", content):
        attrs["fields"].append((m.group(1), m.group(2)))
    # Compute methods
    for m in re.finditer(r"def\s+(_compute_\w+)\s*\(", content):
        attrs["compute_methods"].append(m.group(1))
    # @api.constrains
    for m in re.finditer(r'@api\.constrains\s*\(([^)]+)\)', content):
        args = [x.strip().strip('"\'') for x in m.group(1).split(",")]
        attrs["api_constrains"].extend(args)
    # _sql_constraints (list style)
    m = re.search(r'_sql_constraints\s*=\s*\[([\s\S]*?)\]', content)
    if m:
        for t in re.finditer(r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]*)"\)', m.group(1)):
            attrs["_sql_constraints"].append({"name": t.group(1), "sql": t.group(2), "msg": t.group(3)})
    # models.Constraint (Odoo 19 style)
    for m in re.finditer(r'(\w+)\s*=\s*models\.Constraint\s*\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)', content):
        attrs["models_constraint"].append({"attr": m.group(1), "sql": m.group(2), "msg": m.group(3)})
    # Namespace drift: Plastos vs plasticos
    if attrs["class_name"] and attrs["_name"]:
        cn = attrs["class_name"].lower()
        mn = attrs["_name"].replace(".", "")
        if "plastos" in cn and "plasticos" in mn:
            attrs["namespace_drift"] = f"class={attrs['class_name']} vs _name={attrs['_name']}"
    return attrs


def build_model_index(manifests: dict[str, dict]) -> list[dict]:
    """Build full model index per module."""
    index = []
    for module in manifests:
        manifest = manifests[module]
        mod_path = REPO_ROOT / module
        models_dir = mod_path / "models"
        if not models_dir.is_dir():
            continue
        for model_path in models_dir.glob("*.py"):
            if model_path.name.startswith("__"):
                continue
            content = model_path.read_text(encoding="utf-8")
            attrs = _extract_model_attrs(content)
            if not attrs["_name"] and not attrs["_inherit"]:
                continue
            index.append({
                "module": module,
                "file": str(model_path.relative_to(REPO_ROOT)),
                "manifest_depends": manifest.get("depends", []),
                "installable": manifest.get("installable", True),
                "data_files": manifest.get("data", []),
                "demo_files": manifest.get("demo", []),
                **attrs,
            })
    return index


# ---------------------------------------------------------------------------
# 2. Full XML Index (data + views + security + actions)
# ---------------------------------------------------------------------------

def _parse_xml_record(elem: ET.Element, noupdate: bool) -> dict | None:
    """Extract record info from XML element."""
    if elem.tag != "record":
        return None
    xml_id = elem.get("id")
    model = elem.get("model")
    if not xml_id or not model:
        return None
    fields = []
    refs = []
    evals = []
    inherit_id = None
    for child in elem:
        if child.tag == "field":
            name = child.get("name")
            ref = child.get("ref")
            eval_attr = child.get("eval")
            if name:
                fields.append(name)
            if ref:
                refs.append({"field": name, "ref": ref})
            if eval_attr:
                evals.append({"field": name, "eval": eval_attr})
            if name == "inherit_id" and ref:
                inherit_id = ref
    return {
        "id": xml_id,
        "model": model,
        "noupdate": noupdate,
        "fields": fields,
        "refs": refs,
        "evals": evals,
        "inherit_id": inherit_id,
    }


def build_xml_index(manifests: dict[str, dict]) -> list[dict]:
    """Build XML index from all data/demo files in manifests."""
    index = []
    for module, manifest in manifests.items():
        mod_path = REPO_ROOT / module
        if not mod_path.is_dir():
            continue
        for key in ("data", "demo"):
            for rel_path in manifest.get(key, []):
                if not rel_path.endswith(".xml"):
                    continue
                xml_path = mod_path / rel_path
                if not xml_path.exists():
                    continue
                try:
                    tree = ET.parse(xml_path)
                    root = tree.getroot()
                except ET.ParseError:
                    continue
                # Records inside <data noupdate="...">
                for data in root.findall(".//data"):
                    noupdate = data.get("noupdate", "0") in ("1", "true", "True")
                    for record in data.findall("record"):
                        rec = _parse_xml_record(record, noupdate)
                        if rec:
                            index.append({
                                "module": module,
                                "file": str(xml_path.relative_to(REPO_ROOT)),
                                "load_type": key,
                                **rec,
                            })
                # Records directly under root (no data wrapper) - avoid double-count
                if not root.findall(".//data"):
                    for record in root.findall("record"):
                        rec = _parse_xml_record(record, False)
                        if rec:
                            index.append({
                                "module": module,
                                "file": str(xml_path.relative_to(REPO_ROOT)),
                                "load_type": key,
                                **rec,
                            })
    return index


# ---------------------------------------------------------------------------
# 3. External ID Registry Map (Global Collision Detector)
# ---------------------------------------------------------------------------

def build_external_id_registry(xml_index: list[dict]) -> list[dict]:
    """Flatten all XML IDs for collision detection."""
    registry = []
    for rec in xml_index:
        qualified_id = f"{rec['module']}.{rec['id']}"
        registry.append({
            "qualified_id": qualified_id,
            "module": rec["module"],
            "xml_id": rec["id"],
            "model": rec["model"],
            "noupdate": rec.get("noupdate", False),
            "source_file": rec["file"],
        })
    return registry


# ---------------------------------------------------------------------------
# 4. Dependency Graph + Load Order
# ---------------------------------------------------------------------------

def build_dependency_graph(manifests: dict[str, dict]) -> dict:
    """Compute module install order DAG."""
    deps = {m: set(manifest.get("depends", [])) for m, manifest in manifests.items()}
    order = []
    remaining = set(deps.keys())
    while remaining:
        batch = [m for m in remaining if deps[m].issubset(set(order))]
        if not batch:
            break
        order.extend(sorted(batch))
        remaining -= set(batch)
    if remaining:
        order.extend(sorted(remaining))  # circular deps - best effort
    return {"order": order, "deps": {m: list(d) for m, d in deps.items()}}


# ---------------------------------------------------------------------------
# 5. Odoo 19 Compliance Scan Targets
# ---------------------------------------------------------------------------

def build_compliance_scan(model_index: list[dict], xml_index: list[dict]) -> list[dict]:
    """Identify deprecated patterns for Odoo 19 compliance."""
    issues = []
    for m in model_index:
        if m.get("namespace_drift"):
            issues.append({
                "type": "namespace_drift",
                "file": m["file"],
                "detail": m["namespace_drift"],
            })
        if m.get("_sql_constraints") and isinstance(m["_sql_constraints"], list):
            # Old-style list; Odoo 19 prefers models.Constraint
            issues.append({
                "type": "old_sql_constraints",
                "file": m["file"],
                "model": m["_name"],
                "detail": "Consider models.Constraint for Odoo 19",
            })
    # Scan for self._context (deprecated)
    for manifest_path in REPO_ROOT.glob("*/models/*.py"):
        content = manifest_path.read_text(encoding="utf-8")
        if "self._context" in content:
            issues.append({
                "type": "deprecated_self_context",
                "file": str(manifest_path.relative_to(REPO_ROOT)),
                "detail": "Use self.env.context",
            })
    return issues


# ---------------------------------------------------------------------------
# 6. Transaction Spine Interaction Map
# ---------------------------------------------------------------------------

SPINE_MODULES = {"plasticos_transaction", "plasticos_commission", "plasticos_documents", "plasticos_logistics"}


def build_transaction_spine_map(model_index: list[dict], xml_index: list[dict]) -> dict:
    """Cross-check transaction spine modules."""
    spine_models = [m for m in model_index if m["module"] in SPINE_MODULES]
    spine_xml = [x for x in xml_index if x["module"] in SPINE_MODULES]
    sequences = [x for x in spine_xml if x["model"] == "ir.sequence"]
    return {
        "models": [
            {
                "module": m["module"],
                "name": m["_name"],
                "inherit": m.get("_inherit"),
                "fields_count": len(m.get("fields", [])),
                "constraints": len(m.get("api_constrains", [])) + len(m.get("_sql_constraints", [])) + len(m.get("models_constraint", [])),
            }
            for m in spine_models
        ],
        "sequences": [
            {"module": s["module"], "xml_id": s["id"], "qualified": f"{s['module']}.{s['id']}"}
            for s in sequences
        ],
        "ref_data_seeded": [
            x for x in spine_xml
            if x["model"] in ("res.groups", "ir.rule", "ir.model.access", "ir.cron")
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _is_tracked_module(module: str) -> bool:
    """Exclude test/script/gitignored modules."""
    if module.startswith("tests") or module == "scripts":
        return False
    # Skip if module root is in .gitignore (e.g. l9_trace/, PlasticOS/)
    # Must match full line "module/" or "module" - not "module/subdir/"
    gitignore = REPO_ROOT / ".gitignore"
    if gitignore.exists():
        for line in gitignore.read_text(encoding="utf-8").splitlines():
            line = line.strip().rstrip("/")
            if line == module or line == f"{module}/":
                return False
    return True


def build_migrations_index() -> list[dict]:
    """Index migration scripts."""
    index = []
    for mig_path in REPO_ROOT.glob("*/migrations/*/*.py"):
        parts = mig_path.relative_to(REPO_ROOT).parts
        if len(parts) >= 4:
            module, _, version, fname = parts[0], parts[1], parts[2], parts[3]
            index.append({
                "module": module,
                "version": version,
                "file": str(mig_path.relative_to(REPO_ROOT)),
                "name": fname,
            })
    return index


def build_test_catalog() -> list[dict]:
    """Index test files."""
    index = []
    for path in REPO_ROOT.glob("**/test*.py"):
        if "migrations" in str(path) or "__pycache__" in str(path):
            continue
        rel = path.relative_to(REPO_ROOT)
        index.append({"file": str(rel), "dir": str(rel.parent)})
    return index


def main() -> int:
    manifests = {}
    for manifest_path in REPO_ROOT.glob("*/__manifest__.py"):
        module = manifest_path.parent.name
        if not _is_tracked_module(module):
            continue
        m = _parse_manifest(manifest_path)
        if m:
            manifests[module] = m

    model_index = build_model_index(manifests)
    xml_index = build_xml_index(manifests)
    external_ids = build_external_id_registry(xml_index)
    dep_graph = build_dependency_graph(manifests)
    compliance = build_compliance_scan(model_index, xml_index)
    spine_map = build_transaction_spine_map(model_index, xml_index)
    migrations_index = build_migrations_index()
    test_catalog = build_test_catalog()

    # Write outputs
    def write_json(name: str, data: list | dict) -> None:
        (REPORTS_DIR / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write_txt(name: str, lines: list[str]) -> None:
        (REPORTS_DIR / f"{name}.txt").write_text("\n".join(lines), encoding="utf-8")

    write_json("odoo_model_index", model_index)
    write_json("odoo_xml_index", xml_index)
    write_json("odoo_external_id_registry", external_ids)
    write_json("odoo_dependency_graph", dep_graph)
    write_json("odoo_compliance_scan", compliance)
    write_json("odoo_transaction_spine", spine_map)
    write_json("odoo_migrations", migrations_index)
    write_json("odoo_test_catalog", test_catalog)

    # Human-readable summaries
    lines = []
    lines.append("# Odoo Model Index")
    lines.append("")
    for m in model_index:
        lines.append(f"## {m['module']} :: {m.get('_name', 'N/A')}")
        lines.append(f"  file: {m['file']}")
        lines.append(f"  inherit: {m.get('_inherit', [])}")
        lines.append(f"  fields: {len(m.get('fields', []))}")
        lines.append(f"  constraints: @api.constrains={m.get('api_constrains', [])} _sql={m.get('_sql_constraints', [])} models.Constraint={m.get('models_constraint', [])}")
        if m.get("namespace_drift"):
            lines.append(f"  ⚠ namespace_drift: {m['namespace_drift']}")
        lines.append("")
    write_txt("odoo_model_index", lines)

    lines = []
    lines.append("# External ID Registry (collision detector)")
    lines.append("")
    for r in external_ids:
        lines.append(f"{r['qualified_id']}\t{r['model']}\tnoupdate={r['noupdate']}\t{r['source_file']}")
    write_txt("odoo_external_id_registry", lines)

    lines = []
    lines.append("# Dependency Load Order")
    lines.append("")
    for i, mod in enumerate(dep_graph["order"], 1):
        deps = dep_graph["deps"].get(mod, [])
        lines.append(f"{i}. {mod} (depends: {', '.join(deps)})")
    write_txt("odoo_dependency_order", lines)

    # Summary
    print("## Odoo index updated")
    print("")
    print("| Index | Entries |")
    print("|-------|---------|")
    print(f"| models | {len(model_index)} |")
    print(f"| xml records | {len(xml_index)} |")
    print(f"| external IDs | {len(external_ids)} |")
    print(f"| compliance issues | {len(compliance)} |")
    print(f"| migrations | {len(migrations_index)} |")
    print(f"| test files | {len(test_catalog)} |")
    print("")
    print("**Location:** reports/repo-index/")
    print("")
    print("Files:")
    for f in sorted(REPORTS_DIR.glob("odoo_*")):
        print(f"  - {f.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

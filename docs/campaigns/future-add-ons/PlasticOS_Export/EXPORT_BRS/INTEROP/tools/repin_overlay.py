"""Compute the PlasticOS Export v2.8 re-pin overlay from git objects only (read-only)."""

import ast
import json
import re
import subprocess
import sys
from collections import defaultdict

REPO, PACK, NEW, OUT = sys.argv[1:5]
LEDGER = f"{PACK}/EXPORT_BRS/INTEROP/SOURCE_BOUND_CHANGE_LEDGER_v2.7.5.json"


def git(*args, check=True):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(r.stderr)
    return r.stdout


def blob(rev, path):
    r = subprocess.run(["git", "-C", REPO, "rev-parse", f"{rev}:{path}"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def show(rev, path):
    return git("show", f"{rev}:{path}")


NEW_SHA = git("rev-parse", NEW).strip()
L = json.loads(show(NEW_SHA, LEDGER))
OLD_SHA = L["target"]["head_sha"]
ahead = int(git("rev-list", "--count", f"{OLD_SHA}..{NEW_SHA}").strip())

# -- manifests at NEW
modules = sorted(
    {
        p.split("/")[0]
        for p in git("ls-tree", "-r", "--name-only", NEW_SHA).splitlines()
        if re.fullmatch(r"plasticos_[a-z0-9_]+/__manifest__\.py", p)
    }
)
manifest = {m: ast.literal_eval(show(NEW_SHA, f"{m}/__manifest__.py")) for m in modules}


def bump(v):
    parts = v.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


# -- version re-pin from manifest effects
versions = []
for e in L["effects"]:
    path = e["target_path"]
    if not path.endswith("__manifest__.py") or e["planned_action"] != "EDIT":
        continue
    mod = path.split("/")[0]
    found = sorted(
        set(re.findall(r"19\.0\.\d+\.\d+\.\d+", json.dumps(e))), key=lambda s: [int(x) for x in s.split(".")]
    )
    planned_from, planned_to = found[0], found[-1]
    current = manifest[mod]["version"]
    versions.append(
        {
            "module": mod,
            "effect_id": e["effect_id"],
            "v2_7_5_planned_from": planned_from,
            "v2_7_5_planned_to": planned_to,
            "current_at_repin": current,
            "plan_status": "STALE_ALREADY_PASSED"
            if [int(x) for x in current.split(".")] >= [int(x) for x in planned_to.split(".")]
            else "CURRENT",
            "v2_8_successor": bump(current),
            "rule": "successor = current manifest version with the last component +1, recomputed again at slice start (version-bump skill)",
        }
    )
succ = {v["module"]: v for v in versions}

# -- migration re-target
migrations = []
for e in L["effects"]:
    m = re.fullmatch(r"(plasticos_[a-z0-9_]+)/migrations/(19\.0\.\d+\.\d+\.\d+)/(.+)", e["target_path"])
    if not m or e["planned_action"] != "CREATE":
        continue
    mod, ver, leaf = m.groups()
    new_ver = succ[mod]["v2_8_successor"] if mod in succ else None
    migrations.append(
        {
            "effect_id": e["effect_id"],
            "v2_7_5_path": e["target_path"],
            "v2_8_path": f"{mod}/migrations/{new_ver}/{leaf}" if new_ver else None,
            "v2_7_5_path_state_at_repin": (
                "OCCUPIED_BY_OTHER_WORK_NEVER_OVERWRITE"
                if blob(NEW_SHA, e["target_path"]) is not None
                else "FREE_BUT_SUPERSEDED"
            ),
            "existing_migration_dirs_at_repin": sorted(
                {
                    p.split("/")[2]
                    for p in git("ls-tree", "-r", "--name-only", NEW_SHA, f"{mod}/migrations").splitlines()
                }
                if blob(NEW_SHA, f"{mod}/migrations")
                else []
            ),
        }
    )

# -- ADR
adr_files = [
    p for p in git("ls-tree", "-r", "--name-only", NEW_SHA, "docs/adr").splitlines() if re.match(r"docs/adr/ADR-\d+", p)
]
nums = sorted({int(re.match(r"docs/adr/ADR-(\d+)", p).group(1)) for p in adr_files})
adr129 = [p for p in adr_files if p.startswith("docs/adr/ADR-129")]
adr = {
    "v2_7_5_reserved": "ADR-129-export-physical-evidence-and-owner-contracts",
    "ADR_129_at_repin": adr129,
    "highest_number_at_repin": nums[-1],
    "v2_8_reserved": f"ADR-{nums[-1] + 1:03d}-export-physical-evidence-and-owner-contracts",
    "rule": "re-check the next free number when the ADR is written; never reuse an occupied number",
}

# -- invariants
inv = show(NEW_SHA, "INVARIANTS.md")
inv_ver = re.search(r"\*\*Version:\*\*\s*([0-9.]+)", inv)
invariants = {
    "v2_7_5_cited": "INVARIANTS.md v2.2.0 (constitution) + POS-INV-26 pack-local draft r2",
    "constitution_at_repin": f"INVARIANTS.md v{inv_ver.group(1) if inv_ver else 'UNKNOWN'}",
    "POS_INV_26_in_constitution": "POS-INV-26" in inv,
    "ids_at_repin": sorted(set(re.findall(r"POS-INV-\d+", inv)), key=lambda s: int(s.split("-")[-1])),
    "v2_7_5_ledger_citations": {
        k: json.dumps(L).count(k) for k in sorted(set(re.findall(r"POS-INV-\d+", json.dumps(L))))
    },
    "disposition": (
        "Cite the admitted constitution (INVARIANTS.md at the re-pin head). POS-INV-26 (whole blast radius "
        "before project code) is not admitted: it stays a pack-local gate of this campaign, enforced by "
        "PRE_CODE_RIPPLE_CLOSURE_GATE.md, not cited as constitutional law."
    ),
}

# -- dependency impact at NEW
rev = defaultdict(set)
for m, man in manifest.items():
    for d in man.get("depends", []):
        rev[d].add(m)


def closure(root):
    seen, stack = set(), [root]
    while stack:
        for c in rev[stack.pop()]:
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return seen


edited = sorted(succ)
impact = {}
for mod in edited:
    direct = sorted(rev[mod])
    trans = sorted(closure(mod) - set(direct))
    impact[mod] = {
        "direct_dependents": direct,
        "transitive_dependents": trans,
        "installable_dependents": sorted(d for d in closure(mod) if manifest[d].get("installable", True)),
    }
log = impact.get("plasticos_logistics", {})
dep_delta = {
    "v2_7_5_direct_logistics_dependents": L["direct_logistics_dependents"],
    "v2_7_5_transitive_logistics_dependents": L["known_transitive_logistics_dependents"],
    "added_direct_since_v2_7_5": sorted(set(log.get("direct_dependents", [])) - set(L["direct_logistics_dependents"])),
    "removed_direct_since_v2_7_5": sorted(
        set(L["direct_logistics_dependents"]) - set(log.get("direct_dependents", []))
    ),
}

# -- path drift for every ledger path
drift = []
for f in L["file_dispositions"]:
    p = f["path"]
    old, new = blob(OLD_SHA, p), blob(NEW_SHA, p)
    if p.startswith("native:"):
        state = "INTERFACE_NOT_A_FILE"
    elif old is None and new is None:
        state = "ABSENT_BOTH"
    elif old is None:
        state = "APPEARED_SINCE_V2_7_5"
    elif new is None:
        state = "REMOVED_SINCE_V2_7_5"
    else:
        state = "UNCHANGED" if old == new else "CHANGED"
    drift.append(
        {
            "path": p,
            "file_disposition": f["file_disposition"],
            "owner": f["owner"],
            "drift": state,
            "blob_at_v2_7_5": old,
            "blob_at_repin": new,
        }
    )
summary = defaultdict(lambda: defaultdict(int))
for d in drift:
    summary[d["file_disposition"]][d["drift"]] += 1
reconcile = [
    d
    for d in drift
    if d["drift"] in ("CHANGED", "REMOVED_SINCE_V2_7_5")
    and d["file_disposition"] in ("EDIT", "NO_CHANGE", "REVIEW_ONLY", "BLOCKED", "INDEPENDENT")
]
conflicts = [
    {
        **d,
        "resolution": "v2.8 re-targets this planned file to its module's successor version folder; the existing file is never overwritten",
    }
    for d in drift
    if d["file_disposition"] in ("CREATE", "NO_ADD") and d["drift"] == "APPEARED_SINCE_V2_7_5"
]

# -- private originals still committed
private = [p for p in git("ls-tree", "-r", "--name-only", NEW_SHA, PACK).splitlines() if "PRIVATE_OPERATOR_CASE" in p]
order = show(NEW_SHA, "config/odoo_module_order.yaml")

out = {
    "schema": "plasticos.export.repin-overlay/v1",
    "version": "2.8",
    "overlays": "EXPORT_BRS/INTEROP/SOURCE_BOUND_CHANGE_LEDGER_v2.7.5.json",
    "overlay_rule": "Fields here supersede the v2.7.5 ledger's target, version, migration-path, ADR, invariant and dependent fields. Every other v2.7.5 decision stands until its slice re-census.",
    "target": {
        "repository": "cryptoxdog/IB-Odoo_19",
        "branch": "Staging",
        "v2_7_5_head_sha": OLD_SHA,
        "repin_head_sha": NEW_SHA,
        "commits_since_v2_7_5": ahead,
        "drift_policy": L["target"]["current_head_drift_policy"],
        "method": "local git objects only: git rev-parse <rev>:<path>, manifest literal_eval, ls-tree; no Odoo runtime",
    },
    "status": {
        "gate_0_repin": "DONE_STATIC",
        "gate_0_module_approval": "NOT_GRANTED",
        "code_grant": "NOT_GRANTED",
        "s1_target": "NOT_OBSERVED",
        "code_entry": "BLOCKED_S1_TARGET_EVIDENCE_AND_SEPARATE_AUTHORIZATION",
        "runtime_verification": "NOT_RUN",
    },
    "versions": versions,
    "migrations": migrations,
    "adr": adr,
    "invariants": invariants,
    "dependency_impact": impact,
    "logistics_dependent_delta": dep_delta,
    "path_drift_summary": {k: dict(v) for k, v in summary.items()},
    "paths_requiring_slice_reconcile": [
        {"path": d["path"], "file_disposition": d["file_disposition"], "drift": d["drift"]} for d in reconcile
    ],
    "create_or_no_add_conflicts": conflicts,
    "path_drift": drift,
    "module_order": {
        "export_integration_modules_present": "export_integration_modules" in order,
        "plasticos_export_listed": "plasticos_export" in order,
    },
    "private_originals_committed": {
        "count": len(private),
        "paths": private,
        "pack_instruction": "README: do not commit the private originals",
        "action": "OPERATOR_DECISION_NOT_TAKEN_IN_V2_8",
    },
}
open(OUT, "w").write(json.dumps(out, indent=2, sort_keys=False) + "\n")
print(
    json.dumps(
        {
            "ahead": ahead,
            "versions": [
                (v["module"], v["v2_7_5_planned_to"], v["current_at_repin"], v["v2_8_successor"]) for v in versions
            ],
            "adr": adr["v2_8_reserved"],
            "adr129": adr129,
            "invariants": {k: invariants[k] for k in ("constitution_at_repin", "POS_INV_26_in_constitution")},
            "dep_delta": dep_delta,
            "drift_summary": out["path_drift_summary"],
            "reconcile": len(reconcile),
            "conflicts": len(conflicts),
            "private": len(private),
            "order": out["module_order"],
        },
        indent=1,
    )
)

#!/usr/bin/env python3
"""Source-pinned *declared* planning checks; no independent source or runtime proof."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = [f"ODOO-INV-{i:02}" for i in range(1, 20)] + ["BAN001"]
ACCEPTED = {"OBSERVED", "EVIDENCED_EXCLUSION"}
EDITS = {"CREATE", "EDIT", "REMOVE"}


def plan_digest(obj):
    plan = copy.deepcopy(obj)
    plan.get("authority", {}).pop("plan_acceptance", None)
    plan.get("authority", {}).pop("coding_grant", None)
    plan.pop("readiness", None)
    return hashlib.sha256(
        json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def cycles(graph):
    state, found = {}, []

    def walk(node, trace):
        if state.get(node) == 1:
            found.append(" -> ".join(trace + [node]))
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for p in graph.get(node, []):
            if p in graph:
                walk(p, trace + [node])
        state[node] = 2

    for node in graph:
        walk(node, [])
    return found


def reverse_dependents(roots, snapshot):
    names = {m["name"] for m in snapshot["modules"]}
    reverse = {m: set() for m in names}
    for entry in snapshot["modules"]:
        for dependency in entry["depends"]:
            if dependency in reverse:
                reverse[dependency].add(entry["name"])
    seen, queue = set(roots), list(roots)
    while queue:
        for downstream in reverse.get(queue.pop(), []):
            if downstream not in seen:
                queue.append(downstream)
                seen.add(downstream)
    return seen


def schema_errors(value):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["Missing 'jsonschema' package: full schema validation is required, no subset fallback"]
    schema = json.loads((ROOT / "SCHEMA/case.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return [
        "/".join(map(str, e.absolute_path)) + ": " + e.message for e in Draft202012Validator(schema).iter_errors(value)
    ]


def check(obj, gate="plan", snapshot=None, lock=None):
    errors = schema_errors(obj)
    if errors:
        return errors
    if snapshot is None:
        snapshot = json.loads((ROOT / "SOURCES/REPO_MANIFEST_SNAPSHOT.json").read_text())
    if lock is None:
        lock = json.loads((ROOT / "SOURCES/REPO_SOURCE_LOCK.json").read_text())

    def add(code, msg=""):
        errors.append(code + (": " + msg if msg else ""))

    def require(value, key):
        if not isinstance(value, str) or not value.strip():
            add("EMPTY", key)

    target = obj["target"]
    required_source = lock["revision"]
    if target["repository"] != snapshot["repository"] or target["repository"] != lock["repo"]:
        add("REPOSITORY_MISMATCH")
    if target["revision"] != snapshot["revision"] or target["revision"] != required_source:
        add("SOURCE_DRIFT", "rebind case, source lock and complete manifest census to the same SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", target["revision"]):
        add("REVISION_NOT_IMMUTABLE")
    constitution = target["constitution"]
    verified_const = next((x for x in lock["authority_closure"] if x["path"] == "INVARIANTS.md"), None)
    if not verified_const or (
        constitution["path"],
        constitution["version"],
        constitution["blob_sha"],
        constitution["authority_class"],
    ) != ("INVARIANTS.md", verified_const["version"], verified_const["git_blob_sha"], "CONSTITUTIONAL"):
        add("WRONG_CONSTITUTION", "repo INVARIANTS.md v2.2.0 outranks draft POS candidates")
    original_draft = ROOT / "SOURCES/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md"
    if hashlib.sha256(original_draft.read_bytes()).hexdigest() != lock["candidate_invariant_source"]["sha256"]:
        add("CANDIDATE_SOURCE_TAMPERED")
    if target["installed_target"]["status"] not in ACCEPTED:
        add("TARGET_ENV_UNKNOWN")
    require(target["installed_target"]["evidence"], "target.installed_target.evidence")
    if obj["mode"] == "wip_alignment":
        w = target.get("wip") or {}
        if w.get("head_revision") != target["revision"]:
            add("WIP_WRONG_HEAD")
        for name in ("base_revision", "test_evidence"):
            require(w.get(name), "target.wip." + name)
        if not w.get("capabilities"):
            add("WIP_CAPABILITIES_OMITTED")
        for row in w.get("capabilities", []):
            if row["disposition"] == "BLOCK_UNKNOWN":
                add("WIP_UNRESOLVED_CORRECTION", row["name"])
            for f in ("name", "behavior", "evidence", "preservation_test"):
                require(row[f], "wip.capabilities." + f)
    authority = obj["authority"]
    if authority["open_material_decisions"]:
        add("OPEN_OPERATOR_DECISIONS")
    if (
        authority["operator_blast_radius_gate"]["id"] != "POS-INV-26"
        or not authority["operator_blast_radius_gate"]["applies"]
    ):
        add("POS_INV_26_DISABLED", "operator pre-code closure never optional")
    require(authority["operator_blast_radius_gate"]["source"], "operator_blast_radius_gate.source")
    if gate == "precode":
        for row in authority.get("source_interfaces", []):
            if row["status"] == "PROPOSED":
                add("UNADOPTED_INTERFACE", row["interface"])
    strategy = obj["strategy"]
    for field in (
        "user_problem",
        "outcome",
        "first_proof",
        "best_alternative",
        "reason_selected",
        "reversibility",
        "future_seam",
    ):
        require(strategy[field], "strategy." + field)
    for field in ("now_scope", "non_goals", "native_fit"):
        if not strategy[field]:
            add("MISSING_STRATEGY", field)
    census = obj["source_census"]
    require(census["search_scope"], "source_census.search_scope")
    if not census["methods"]:
        add("MISSING_SEARCH_METHODS")
    if not census["root_modules"]:
        add("NO_CHANGE_ROOTS")
    names = {m["name"] for m in snapshot["modules"]}
    dag = {m["name"]: [d for d in m["depends"] if d in names] for m in snapshot["modules"]}
    if cycles(dag):
        add("SOURCE_MANIFEST_CYCLE", str(cycles(dag)))
    if snapshot["module_count"] != len(names) or len(names) != len(snapshot["modules"]):
        add("BAD_MANIFEST_CENSUS")
    for m in census["root_modules"]:
        if m not in names and not (
            obj["mode"] == "new_addon"
            and m.startswith("plasticos_")
            and any(n["decision"] == "NEW_ADDON" for n in strategy["native_fit"])
        ):
            add("UNKNOWN_ROOT_MODULE", m)
    reachable = reverse_dependents(census["root_modules"], snapshot)
    dispositions = census["module_dispositions"]
    seen = [r["module"] for r in dispositions]
    if len(seen) != len(set(seen)):
        add("DUPLICATE_MODULE_IMPACT")
    if reachable - set(seen):
        add("UNACCOUNTED_REVERSE_DEPENDENTS", ", ".join(sorted(reachable - set(seen))))
    for entry in dispositions:
        for field in ("reason", "evidence", "test_obligation"):
            require(entry[field], "module_impact." + field)
    for entry in census["extra_consumers"]:
        for field in ("reason", "evidence", "test_obligation"):
            require(entry[field], "extra_consumers." + field)
    if census["runtime_consumers"]["status"] not in ACCEPTED:
        add("UNEXPLORED_DYNAMIC_CONSUMERS")
    require(census["runtime_consumers"]["evidence"], "runtime_consumers.evidence")
    if gate == "precode" and census["limits"]:
        add("OPEN_SOURCE_LIMITS", str(census["limits"]))
    inv = obj["invariants"]
    active = inv["constitutional"]
    ids = [x["id"] for x in active]
    if sorted(ids) != sorted(CANONICAL):
        add("WRONG_ACTIVE_INVARIANT_CENSUS", "19 numbered constitutional provisions and BAN001")
    for row in active:
        src = "INVARIANTS.md#BAN001" if row["id"] == "BAN001" else f"INVARIANTS.md#{int(row['id'][-2:])}"
        if row["source"] != src:
            add("WRONG_INVARIANT_REFERENCE", row["id"])
        if row["status"] == "UNASSESSED":
            add("UNASSESSED_ACTIVE_INVARIANT", row["id"])
        require(row["basis"], row["id"] + ".basis")
        if row["status"] == "NOT_APPLICABLE_WITH_EVIDENCE":
            require(row["evidence"], row["id"] + ".evidence")
        if row["id"] == "BAN001" and row["status"] != "APPLIES":
            add("BAN001_CANNOT_BE_EXCLUDED")
    draft = inv["candidate_screening"]
    if draft["status"] != "SCREENED":
        add("PROPOSED_INVARIANT_SCREEN_UNDONE")
    require(draft["basis"], "candidate_screening.basis")
    if draft["source"] != "SOURCES/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md":
        add("DRAFT_MISCLASSIFIED")
    if any(not re.fullmatch(r"POS-INV-(0[1-9]|1[0-9]|2[0-5])", i) for i in draft["relevant_ids"]):
        add("UNKNOWN_DRAFT_INVARIANT")
    effects = obj["effects"]
    if not effects:
        add("NO_MATERIAL_EFFECTS_DECLARED")
    effect_ids = [e["id"] for e in effects]
    if len(effect_ids) != len(set(effect_ids)):
        add("DUPLICATE_EFFECT_ID")
    ep = {e["id"]: e for e in effects}
    for e in effects:
        pref = "effect " + e["id"]
        for field in ("owner", "consumer", "before", "after", "migration", "recovery", "security_impact"):
            require(e[field], pref + "." + field)
        for field in ("reachability", "proof_ids", "invalidators"):
            if not e[field]:
                add("MISSING_EFFECT_OBLIGATION", pref + "." + field)
        r = e["source"]
        if r["status"] != "PROPOSED_NEW" and r["revision"] != target["revision"]:
            add("STALE_EFFECT_SOURCE", pref)
        if r["status"] == "PROPOSED_NEW" and e["disposition"] not in ("CREATE", "NO_ADD"):
            add("NEW_SOURCE_FALSE_OBSERVATION", pref)
        if r["status"] != "PROPOSED_NEW" and r["path"].startswith("plasticos_") and not r.get("git_blob_sha"):
            add("MISSING_EXACT_BLOB", pref)
        if e["disposition"] in EDITS:
            if not e["paths"]:
                add("UNPLANNED_CHANGE_FILE", pref)
        else:
            if e["paths"]:
                add("NO_CHANGE_HAS_EDITS", pref)
            require(e["no_change_basis"], pref + ".no_change_basis")
        for d in e["depends_on"]:
            if d not in ep:
                add("MISSING_EFFECT_DEPENDENCY", pref + " -> " + d)
    if cycles({e["id"]: e["depends_on"] for e in effects}):
        add("CYCLIC_EFFECT_PLAN")
    delivery = obj["delivery"]
    for name in ("migration_plan", "recovery_plan", "release_boundary"):
        require(delivery[name], "delivery." + name)
    units = delivery["units"]
    if not units:
        add("MISSING_IMPLEMENTATION_UNITS")
    unitgraph = {u["id"]: u["depends_on"] for u in units}
    if cycles(unitgraph):
        add("CYCLIC_UNIT_PLAN")
    allocations = [i for u in units for i in u["effect_ids"]]
    if set(allocations) != set(effect_ids) or len(allocations) != len(effect_ids):
        add("EFFECTS_NOT_ASSIGNED_EXACTLY_ONCE")
    for u in units:
        if not u["effect_ids"]:
            add("EMPTY_IMPLEMENTATION_UNIT", u["id"])
        for d in u["depends_on"]:
            if d not in unitgraph:
                add("UNKNOWN_UNIT_DEPENDENCY", d)

    def predecessors(uid):
        out, todo = set(), list(unitgraph.get(uid, []))
        while todo:
            n = todo.pop()
            if n in out:
                continue
            out.add(n)
            todo.extend(unitgraph.get(n, []))
        return out

    u_by_e = {eid: u["id"] for u in units for eid in u["effect_ids"]}
    for e in effects:
        for d in e["depends_on"]:
            if (
                e["id"] in u_by_e
                and d in u_by_e
                and u_by_e[e["id"]] != u_by_e[d]
                and u_by_e[d] not in predecessors(u_by_e[e["id"]])
            ):
                add("UNORDERED_CROSS_UNIT_DEPENDENCY", e["id"] + " -> " + d)
    proofs = delivery["proofs"]
    pids = [p["id"] for p in proofs]
    if len(set(pids)) != len(pids):
        add("DUPLICATE_PROOF_ID")
    for e in effects:
        for p in e["proof_ids"]:
            if p not in pids:
                add("MISSING_EFFECT_PROOF", e["id"] + " -> " + p)
    for p in proofs:
        for field in ("positive", "negative", "owner"):
            require(p[field], p["id"] + "." + field)
        if p["status"] == "OBSERVED_PASS":
            require(p["evidence"], p["id"] + ".evidence")
        if gate == "precode" and p["stage"] == "PRECODE" and p["status"] != "OBSERVED_PASS":
            add("PRECODE_PROOF_NOT_OBSERVED", p["id"])
    if gate == "precode":
        # JSON declarations cannot authenticate human authority. The real host must
        # check the operator grant/receipt independently before code begins.
        add("EXTERNAL_AUTHENTICATION_REQUIRED", "offline planning tool never authorizes coding")
        sha = plan_digest(obj)
        for field in ("plan_acceptance", "coding_grant"):
            entry = authority[field]
            if not entry["granted"] or entry["digest"] != sha or not (entry.get("basis") or entry.get("scope")):
                add("UNAUTHENTICATED_OR_STALE_GRANT", field)
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", type=Path)
    p.add_argument("--gate", choices=("plan", "precode"), default="plan")
    p.add_argument("--snapshot", type=Path)
    p.add_argument("--source-lock", type=Path)
    a = p.parse_args()
    try:
        obj = json.loads(a.case.read_text(encoding="utf-8"))
        snap = json.loads(a.snapshot.read_text()) if a.snapshot else None
        lock = json.loads(a.source_lock.read_text()) if a.source_lock else None
        errors = check(obj, a.gate, snap, lock)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        sys.exit(2)
    print(
        json.dumps(
            {
                "gate": a.gate,
                "status": "DECLARED_ACCOUNTING_PASS" if not errors else "FAIL",
                "errors": errors,
                "plan_digest_sha256": plan_digest(obj),
                "caveat": "No real GitHub/DB/Enterprise access, no independent completeness proof, and no approval authentication are performed by this local validator.",
            },
            indent=2,
        )
    )
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()

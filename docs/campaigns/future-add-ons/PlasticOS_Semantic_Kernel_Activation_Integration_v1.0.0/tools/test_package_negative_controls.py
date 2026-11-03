#!/usr/bin/env python3
"""Synthetic tests of package assertions only, never product/runtime tests."""

import copy
import json
from pathlib import Path

from validate_package import records_errors

root = Path(__file__).resolve().parents[1]
paths = [
    "case.json",
    "PLAN/CROSS_REPO_PLAN.json",
    "PLAN/DELIVERY_GRAPH.json",
    "PLAN/ACTIVATION_STATE.json",
    "PLAN/INTENT_TRACE.json",
]
original = [json.loads((root / p).read_text()) for p in paths]
assert not records_errors(*original)
mutations = [
    ("activation set true", lambda a: a[3].update(production_enabled=True)),
    ("fake runtime proof", lambda a: a[0]["delivery"]["proofs"][0].update(status="OBSERVED_PASS")),
    ("missing evidence obligation", lambda a: a[0]["effects"][0].update(proof_ids=["MISSING"])),
    ("missing effect accounting", lambda a: a[2]["nodes"][1].update(effects=[])),
    ("cycle in delivery", lambda a: a[2]["edges"].append({"source": "U12", "target": "U00", "relation": "requires"})),
    ("uncovered operator decision", lambda a: a[4]["coverage"].pop()),
    ("fake coding authorization", lambda a: a[0]["authority"]["coding_grant"].update(granted=True)),
    (
        "dangling graph node",
        lambda a: a[2]["edges"].append({"source": "GHOST", "target": "U12", "relation": "requires"}),
    ),
]
results = []
for name, fn in mutations:
    a = copy.deepcopy(original)
    fn(a)
    errors = records_errors(*a)
    assert errors, name
    results.append({"case": name, "result": "REJECTED_AS_REQUIRED", "errors": errors})
print(
    json.dumps(
        {
            "status": "PASS_SYNTHETIC_PACKAGE_CONTROLS",
            "tests": len(results),
            "results": results,
            "product_runtime_tests": "NOT_RUN",
        },
        indent=2,
    )
)

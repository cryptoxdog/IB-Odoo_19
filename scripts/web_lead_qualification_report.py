#!/usr/bin/env python3
"""Compare legacy HOT/COLD routing and validated qualification against broker labels.

Input 1: a JSON list of web leads exported from a database running
``qualification_mode = shadow`` (or ``live``), each row carrying ``lead_id``,
``decision``, ``state``, and ``decision_reasons``. Export it in ``odoo-bin shell``:

    import json
    rows = env["plasticos.web.lead"].search_read(
        [("decision_reasons", "!=", False)], ["lead_id", "decision", "state", "decision_reasons"]
    )
    print(json.dumps(rows, default=str))

Input 2: a CSV with columns ``lead_id,label[,rationale]``. A label is ``hot``,
``review``, ``cold``, or ``unknown``, assigned by a broker on business value
(plan A3). The current classifier's decision is never a label.

The report never writes to a database and carries no contact data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

LABELS = ("hot", "review", "cold")


def _qualification(row: Mapping[str, Any]) -> Mapping[str, Any]:
    reasons = row.get("decision_reasons")
    if isinstance(reasons, str):
        try:
            reasons = json.loads(reasons)
        except ValueError:
            reasons = {}
    reasons = reasons if isinstance(reasons, Mapping) else {}
    qualification = reasons.get("qualification")
    return qualification if isinstance(qualification, Mapping) else {}


def _rates(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Business-quality measures for (label, predicted) pairs with a known label."""
    valuable = [predicted for label, predicted in pairs if label in ("hot", "review")]
    predicted_hot = [label for label, predicted in pairs if predicted == "hot"]
    junk = [predicted for label, predicted in pairs if label == "cold"]
    return {
        "labelled": len(pairs),
        "confusion": {f"{label}->{predicted}": count for (label, predicted), count in sorted(Counter(pairs).items())},
        "valuable_lead_recall": round(sum(p != "cold" for p in valuable) / len(valuable), 3) if valuable else None,
        "false_cold_rate": round(sum(p == "cold" for p in valuable) / len(valuable), 3) if valuable else None,
        "hot_precision": round(sum(lb == "hot" for lb in predicted_hot) / len(predicted_hot), 3)
        if predicted_hot
        else None,
        "false_hot_rate": round(sum(p == "hot" for p in junk) / len(junk), 3) if junk else None,
        "review_rate": round(sum(p == "review" for _, p in pairs) / len(pairs), 3) if pairs else None,
        "known_valuable_silently_cold": sum(p == "cold" for p in valuable),
    }


def build_report(rows: Iterable[Mapping[str, Any]], labels: Mapping[str, str]) -> dict[str, Any]:
    """Legacy versus validated qualification on the same frozen, labelled corpus."""
    per_lead = []
    legacy_pairs: list[tuple[str, str]] = []
    proposed_pairs: list[tuple[str, str]] = []
    unavailable = 0
    for row in rows:
        qualification = _qualification(row)
        if not qualification:
            continue
        lead_id = str(row.get("lead_id") or "")
        legacy = str(qualification.get("legacy_decision") or "")
        proposed = str(qualification.get("final_disposition") or "")
        if qualification.get("model_recommendation") is None:
            unavailable += 1
        label = (labels.get(lead_id) or "unknown").strip().lower()
        per_lead.append(
            {
                "lead_id": lead_id,
                "label": label,
                "legacy": legacy,
                "recommendation": qualification.get("model_recommendation"),
                "proposed": proposed,
                "overridden": bool(qualification.get("overridden")),
                "routing_mode": qualification.get("routing_mode"),
            }
        )
        if label in LABELS:
            legacy_pairs.append((label, legacy))
            proposed_pairs.append((label, proposed))
    return {
        "leads_with_qualification": len(per_lead),
        "assessment_unavailable": unavailable,
        "legacy": _rates(legacy_pairs),
        "proposed": _rates(proposed_pairs),
        "proposed_review_workload": sum(item["proposed"] == "review" for item in per_lead),
        "per_lead": per_lead,
        "go_live_blockers": _blockers(_rates(proposed_pairs)),
    }


def _blockers(proposed: Mapping[str, Any]) -> list[str]:
    """Plan H5: conditions that forbid switching to live."""
    blockers = []
    if not proposed["labelled"]:
        blockers.append("No broker-labelled leads: a rate without a labelled corpus is not acceptance evidence.")
    if proposed["known_valuable_silently_cold"]:
        blockers.append(f"{proposed['known_valuable_silently_cold']} broker-valued lead(s) would be COLD.")
    if proposed["false_hot_rate"]:
        blockers.append(f"Clearly unsuitable leads would be HOT (rate {proposed['false_hot_rate']}).")
    return blockers


def _read_labels(path: str) -> dict[str, str]:
    with open(path, newline="", encoding="utf-8") as handle:
        return {row["lead_id"].strip(): row.get("label", "") for row in csv.DictReader(handle) if row.get("lead_id")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("leads_json")
    parser.add_argument("labels_csv")
    args = parser.parse_args(argv)
    with open(args.leads_json, encoding="utf-8") as handle:
        rows = json.load(handle)
    report = build_report(rows, _read_labels(args.labels_csv))
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 1 if report["go_live_blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

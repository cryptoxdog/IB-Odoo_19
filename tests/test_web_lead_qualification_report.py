"""Shadow-period comparison report for web-lead qualification (plan A4 / H4 / H5)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "web_lead_qualification_report.py"
_spec = importlib.util.spec_from_file_location("web_lead_qualification_report", _PATH)
report_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report_module)


def _row(lead_id, legacy, final, recommendation="hot"):
    return {
        "lead_id": lead_id,
        "decision": legacy,
        "decision_reasons": {
            "qualification": {
                "legacy_decision": legacy,
                "final_disposition": final,
                "model_recommendation": recommendation,
                "overridden": recommendation != final,
                "routing_mode": "shadow",
            }
        },
    }


def test_report_compares_legacy_and_proposed_on_broker_labels():
    rows = [
        _row("A", "cold", "hot"),
        _row("B", "cold", "review"),
        _row("C", "cold", "cold", recommendation="cold"),
        _row("D", "hot", "hot"),
        _row("E", "cold", "review", recommendation=None),
        {"lead_id": "F", "decision_reasons": {}},
    ]
    labels = {"A": "hot", "B": "review", "C": "cold", "D": "hot", "E": "unknown"}
    report = report_module.build_report(rows, labels)

    assert report["leads_with_qualification"] == 5
    assert report["assessment_unavailable"] == 1
    assert report["legacy"]["known_valuable_silently_cold"] == 2
    assert report["legacy"]["false_cold_rate"] == round(2 / 3, 3)
    assert report["proposed"]["known_valuable_silently_cold"] == 0
    assert report["proposed"]["hot_precision"] == 1.0
    assert report["proposed"]["false_hot_rate"] == 0.0
    assert report["proposed_review_workload"] == 2
    assert report["go_live_blockers"] == []


def test_no_labels_is_a_go_live_blocker():
    report = report_module.build_report([_row("A", "cold", "hot")], {})
    assert report["go_live_blockers"]


def test_false_hot_blocks_go_live():
    report = report_module.build_report([_row("J", "cold", "hot")], {"J": "cold"})
    assert any("unsuitable" in item for item in report["go_live_blockers"])

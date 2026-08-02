"""M4 / TASK-049 — Gate writeback + provenance contracts preserved at source level."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "plasticos_enrichment/models/enrichment_run.py"


def test_gate_converge_helpers_present():
    src = RUN.read_text(encoding="utf-8")
    assert "_run_gate_converge" in src
    assert "_apply_converge_writeback" in src
    assert "gate_auto_writeback_enabled" in src
    assert "send_converge_action" in src


def test_writeback_merge_not_overwrite_documented():
    src = RUN.read_text(encoding="utf-8")
    assert (
        "merge-not-overwrite" in src.lower()
        or "merge_not_overwrite" in src
        or "never clobber" in src.lower()
        or "Existing" in src
    )
    assert "engine_used" in src
    assert "gate_packet_id" in src

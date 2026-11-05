#!/usr/bin/env python3
"""
Baseline/allowlist helpers for the audit scanners.

Why this exists: comparing raw CRITICAL/HIGH *counts* against a baseline
number (the previous approach) can't tell "one known false positive got
fixed and one new real bug appeared" apart from "nothing changed" — the
count stays flat either way. Fingerprinting each finding and diffing
against a checked-in allowlist (ci/baselines/*.json) closes that gap: any
finding not already in the log is treated as new and fails the gate,
regardless of whether the total count moved.

Workflow this enables (per user instruction — log known findings, don't
keep re-patching the scanner):
  1. A scanner flags something.
  2. A human reviews it: genuine bug -> fix the code. False positive or
     accepted/tracked debt -> add its entry to the matching ci/baselines/*.json
     file (see check_baseline.py --dump-new for ready-to-paste JSON).
  3. The scanner itself is never edited to special-case that finding — only
     the log grows.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# Fields checked, in order, for a stable identity beyond type+file. Schema-level
# findings (odoo_audit.py) carry model/field/compute_method/method and have no
# line-number dependency at all. Pattern-level findings (performance_audit.py,
# security_audit.py) have no model/field, so we fall back to the exact offending
# source line — stable against unrelated edits elsewhere in the file, but an edit
# to the flagged line itself is (correctly) treated as a new finding.
_IDENTITY_FIELDS = ("model", "field", "compute_method", "method")


def compute_fingerprint(finding: dict[str, Any]) -> str:
    """Stable identity for a finding, independent of line-number drift."""
    parts = [finding.get("type", ""), finding.get("file", "")]
    for key in _IDENTITY_FIELDS:
        if finding.get(key):
            parts.append(f"{key}={finding[key]}")
    if finding.get("code"):
        parts.append(str(finding["code"]))
    elif finding.get("message"):
        parts.append(str(finding["message"]))
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_baseline(path: Path) -> dict[str, dict[str, Any]]:
    """Load a ci/baselines/*.json allowlist -> {fingerprint: entry}."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {entry["fingerprint"]: entry for entry in data.get("entries", [])}


def diff_findings(
    findings: list[dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Split findings into (known, new) against the baseline; also return
    fingerprints present in the baseline but absent from current findings
    (stale entries — the underlying issue was likely fixed; safe to prune,
    never required to unblock CI)."""
    known: list[dict[str, Any]] = []
    new: list[dict[str, Any]] = []
    seen: set[str] = set()

    for finding in findings:
        fp = compute_fingerprint(finding)
        finding["_fingerprint"] = fp
        seen.add(fp)
        if fp in baseline:
            known.append(finding)
        else:
            new.append(finding)

    stale = [fp for fp in baseline if fp not in seen]
    return known, new, stale


def baseline_entry(finding: dict[str, Any]) -> dict[str, Any]:
    """Build a ci/baselines/*.json entry from a live finding — human-readable
    fields only (no full finding dump) so the log stays reviewable in a PR diff."""
    return {
        "fingerprint": finding["_fingerprint"],
        "type": finding.get("type", ""),
        "severity": finding.get("severity", ""),
        "file": finding.get("file", ""),
        "line": finding.get("line"),
        "model": finding.get("model"),
        "field": finding.get("field"),
        "message": finding.get("message", ""),
    }

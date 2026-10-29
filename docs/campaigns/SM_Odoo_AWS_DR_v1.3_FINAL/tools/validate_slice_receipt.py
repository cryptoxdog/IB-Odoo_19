#!/usr/bin/env python3
"""Local structural sanity for operator-produced contract receipts.

This does not authenticate a provider, test evidence or external authority.
The human/independent verifier still validates cited real evidence.
Requires PyYAML on the executor; document and verify that dependency before use.
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    raise SystemExit("PyYAML not installed; verify approved environment dependency before running") from None

LEGAL = {"NOT_STARTED", "ACTIVE", "PASS", "FAIL", "BLOCKED_EXTERNAL"}
REQUIRED_TOP = {
    "schema",
    "campaign_id",
    "contract_id",
    "contract_revision_sha256",
    "status",
    "observation_utc",
    "source",
    "permissions_and_code",
    "validation",
    "handoff",
}


def check(data):
    if not isinstance(data, dict):
        raise AssertionError("receipt is not a mapping")
    if not REQUIRED_TOP.issubset(data):
        raise AssertionError("missing receipt top-level keys")
    if data["schema"] != "sm.odoosh.dr.slice-receipt/local-v1":
        raise AssertionError("wrong local receipt version")
    if data["campaign_id"] != "SM-ODOO-DR-CAMPAIGN-001":
        raise AssertionError("wrong campaign")
    if not re.fullmatch(r"0[0-6]", str(data["contract_id"])):
        raise AssertionError("contract_id must be exact 00-06")
    if data["status"] not in LEGAL:
        raise AssertionError("invalid status")
    if data["status"] == "PASS":
        sha = str(data.get("contract_revision_sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise AssertionError("contract hash is not pinned")
        if not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)", str(data["observation_utc"])
        ):
            raise AssertionError("observation time missing")
        for key in ("source", "validation", "handoff", "permissions_and_code"):
            if not isinstance(data[key], dict):
                raise AssertionError(f"{key} malformed")
        src = data["source"]
        val = data["validation"]
        handoff = data["handoff"]
        if not re.fullmatch(r"[0-9a-f]{40}", str(src.get("repository_sha", ""))):
            raise AssertionError("repository SHA missing")
        if not val.get("observed_real_checks") or not val.get("observed_negative_tests"):
            raise AssertionError("real and negative test refs mandatory for PASS")
        if data["contract_id"] in ("02", "03", "04", "05", "06") and val.get("immutable_dependency_closed") is not True:
            raise AssertionError("immutable dependency closure cannot be false or unknown")
        if (
            not handoff.get("independent_consumer_ready")
            or handoff.get("open_in_scope_items")
            or handoff.get("externally_blocked_items")
        ):
            raise AssertionError("handoff not closed")
        if not handoff.get("cleanup_and_rotation_complete"):
            raise AssertionError("cleanup/rotation missing")
        if str(handoff.get("private_evidence_repository_reference", "")).startswith("UNKNOWN"):
            raise AssertionError("missing private evidence reference")
        if handoff.get("tested_capability_level") not in ("NATIVE", "INDEPENDENT_DAILY", "INCREMENTAL", "TWO_HOUR"):
            raise AssertionError("capability level not declared")
        if data["contract_id"] in ("02", "03", "04", "05", "06") and str(
            val.get("actual_deployed_recovery_release_digest", "")
        ).startswith("UNKNOWN"):
            # 02 may still use synthetic IaC code source, 05/06 may use final release.
            if data["contract_id"] != "02":
                raise AssertionError("release digest missing")
        if data["contract_id"] in ("03", "04", "05", "06") and str(
            val.get("independent_restore_reference", "")
        ).startswith("UNKNOWN"):
            raise AssertionError("recovery witness missing")
        if data["contract_id"] in ("05", "06") and str(
            handoff.get("operator_emergency_pack_version_and_digest", "")
        ).startswith("UNKNOWN"):
            raise AssertionError("emergency custody proof missing")
        if data["contract_id"] == "04":
            if handoff.get("tested_capability_level") != "TWO_HOUR":
                raise AssertionError("04 cannot PASS without full two-hour target")
            rpo = val.get("measured_business_rpo_minutes")
            if not isinstance(rpo, (int, float)) or isinstance(rpo, bool) or rpo < 0 or rpo > 120:
                raise AssertionError(
                    "04 requires a measured observed <=120-minute business-hours RPO, not a schedule assertion"
                )
        if data["contract_id"] in ("02", "03", "04", "06") and not val.get("verified_protected_s3_versions"):
            raise AssertionError("protected S3 proof missing")
        if data["contract_id"] in ("05", "06") and not data["permissions_and_code"].get(
            "protected_1password_item_ids_only"
        ):
            raise AssertionError("real 1Password custody item references missing")
    elif data["status"] == "BLOCKED_EXTERNAL":
        blocked = data.get("handoff", {}).get("externally_blocked_items") or []
        if not blocked or not data.get("handoff", {}).get("next_action_or_campaign_exit"):
            raise AssertionError("unowned external blocker")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tools/validate_slice_receipt.py receipt.yaml")
    obj = yaml.safe_load(Path(sys.argv[1]).read_text("utf-8"))
    try:
        check(obj)
    except AssertionError as exc:
        raise SystemExit("RECEIPT_STRUCTURAL_FAIL: " + str(exc)) from exc
    print("RECEIPT_STRUCTURAL_PASS: NOT proof of real provider execution")

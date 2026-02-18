# ============================================================
# File: integrity_audit.py
# Module: plasticos_dev_tools
# Version: 19.0.1.0.0
# Author: PlasticOS
# Purpose: Read-only integrity audit for PlasticOS models.
#          Validates referential integrity, orphan records,
#          and compliance rule consistency.
# Usage: Run via Odoo shell:
#   odoo shell -d <db> --addons-path=<path>
#   >>> exec(open('plasticos_dev_tools/tools/integrity_audit.py').read())
#   >>> run_integrity_audit(env)
# ============================================================
"""
Integrity Audit Tool
====================
Read-only audit that checks:
1. Orphaned documents (no matching transaction or load)
2. Transactions with missing compliance rules
3. Loads stuck in intermediate states beyond SLA
4. Document rules referencing non-existent models
5. Duplicate document tag codes

This script performs NO writes. It only reads and reports.
"""

import logging

_logger = logging.getLogger(__name__)


def run_integrity_audit(env):
    """Execute a full read-only integrity audit.

    Args:
        env: Odoo environment (from shell or cron context).

    Returns:
        dict: Audit results with counts and details per check.
    """
    results = {
        "orphaned_documents": [],
        "missing_compliance_rules": [],
        "stuck_loads": [],
        "invalid_rule_models": [],
        "duplicate_tag_codes": [],
    }

    print("=" * 60)
    print("PLASTICOS INTEGRITY AUDIT")
    print("=" * 60)

    # ── Check 1: Orphaned Documents ────────────────────────────
    print("\n[1/5] Checking for orphaned documents...")
    documents = env["plasticos.document"].search([("active", "=", True)])
    for doc in documents:
        try:
            target = env[doc.res_model].browse(doc.res_id)
            if not target.exists():
                results["orphaned_documents"].append({
                    "doc_id": doc.id,
                    "doc_name": doc.name,
                    "res_model": doc.res_model,
                    "res_id": doc.res_id,
                })
        except (KeyError, ValueError):
            results["orphaned_documents"].append({
                "doc_id": doc.id,
                "doc_name": doc.name,
                "res_model": doc.res_model,
                "res_id": doc.res_id,
                "error": "Model not found in registry",
            })
    print("  Found %d orphaned documents." % len(results["orphaned_documents"]))

    # ── Check 2: Transactions Without Compliance Rules ─────────
    print("\n[2/5] Checking transactions without compliance rules...")
    rules = env["plasticos.document.rule"].search([
        ("res_model", "=", "plasticos.transaction"),
        ("active", "=", True),
    ])
    if not rules:
        results["missing_compliance_rules"].append(
            "No active compliance rules found for plasticos.transaction"
        )
    print("  Active rules: %d" % len(rules))

    # ── Check 3: Stuck Loads ───────────────────────────────────
    print("\n[3/5] Checking for loads stuck beyond SLA...")
    from odoo import fields as odoo_fields
    now = odoo_fields.Datetime.now()
    sla_hours = {
        "awaiting_ready": 48,
        "ready_confirmed": 24,
        "rate_confirmed": 24,
        "scheduled": 24,
        "dispatched": 72,
    }
    loads = env["plasticos.load"].search([
        ("state", "in", list(sla_hours.keys())),
    ])
    for load in loads:
        if not load.entered_state_at:
            continue
        limit = sla_hours.get(load.state, 0)
        delta = (now - load.entered_state_at).total_seconds() / 3600
        if delta > limit:
            results["stuck_loads"].append({
                "load_id": load.id,
                "load_name": load.name,
                "state": load.state,
                "hours_stuck": round(delta, 1),
                "sla_limit": limit,
            })
    print("  Found %d loads beyond SLA." % len(results["stuck_loads"]))

    # ── Check 4: Invalid Rule Model References ─────────────────
    print("\n[4/5] Checking for invalid rule model references...")
    all_rules = env["plasticos.document.rule"].search([("active", "=", True)])
    for rule in all_rules:
        if rule.res_model not in env:
            results["invalid_rule_models"].append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "res_model": rule.res_model,
            })
    print("  Found %d invalid model references." % len(results["invalid_rule_models"]))

    # ── Check 5: Duplicate Tag Codes ───────────────────────────
    print("\n[5/5] Checking for duplicate document tag codes...")
    tags = env["plasticos.document.tag"].search([("active", "=", True)])
    code_counts = {}
    for tag in tags:
        code_counts.setdefault(tag.code, []).append(tag.id)
    for code, ids in code_counts.items():
        if len(ids) > 1:
            results["duplicate_tag_codes"].append({
                "code": code,
                "tag_ids": ids,
                "count": len(ids),
            })
    print("  Found %d duplicate tag codes." % len(results["duplicate_tag_codes"]))

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    total_issues = sum(len(v) for v in results.values())
    for key, items in results.items():
        status = "PASS" if not items else "FAIL (%d)" % len(items)
        print("  %-30s %s" % (key, status))
    print("\nTotal issues: %d" % total_issues)

    return results

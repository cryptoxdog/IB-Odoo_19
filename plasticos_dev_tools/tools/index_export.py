# ============================================================
# File: index_export.py
# Module: plasticos_dev_tools
# Version: 19.0.1.0.0
# Author: PlasticOS
# Purpose: Export a complete module index: models, fields,
#          methods, cron jobs, security groups, and views.
# Usage: Run via Odoo shell:
#   odoo shell -d <db> --addons-path=<path>
#   >>> exec(open('plasticos_dev_tools/tools/index_export.py').read())
#   >>> export_index(env)
# ============================================================
"""
Module Index Export Tool
========================
Generates a structured index of all PlasticOS modules for
documentation, onboarding, and audit purposes.

Exports:
1. Model registry (name, description, field count)
2. Cron job inventory (name, model, interval, active)
3. Security group inventory (name, implied groups)
4. Custom field inventory (x_ prefixed fields per model)

Output: Printed to console and returned as dict.
This script performs NO writes. It only reads and reports.
"""

import logging

_logger = logging.getLogger(__name__)

_PLASTICOS_PREFIXES = [
    "plasticos.",
]


def export_index(env):
    """Export a complete index of all PlasticOS models and metadata.

    Args:
        env: Odoo environment.

    Returns:
        dict: Structured index data.
    """
    index = {
        "models": [],
        "crons": [],
        "groups": [],
        "custom_fields": [],
    }

    print("=" * 60)
    print("PLASTICOS MODULE INDEX EXPORT")
    print("=" * 60)

    # ── Models ─────────────────────────────────────────────────
    print("\n[1/4] Indexing PlasticOS models...")
    ir_models = env["ir.model"].search([])
    for m in ir_models:
        if any(m.model.startswith(p) for p in _PLASTICOS_PREFIXES):
            field_count = len(m.field_id)
            index["models"].append({
                "model": m.model,
                "name": m.name,
                "fields": field_count,
            })
            print("  %-45s %3d fields" % (m.model, field_count))
    print("  Total: %d models" % len(index["models"]))

    # ── Cron Jobs ──────────────────────────────────────────────
    print("\n[2/4] Indexing PlasticOS cron jobs...")
    crons = env["ir.cron"].search([])
    for cron in crons:
        model_name = cron.model_id.model if cron.model_id else ""
        if any(model_name.startswith(p) for p in _PLASTICOS_PREFIXES):
            index["crons"].append({
                "name": cron.name,
                "model": model_name,
                "interval": "%d %s" % (cron.interval_number, cron.interval_type),
                "active": cron.active,
            })
            status = "ACTIVE" if cron.active else "INACTIVE"
            print("  [%s] %s" % (status, cron.name))
    print("  Total: %d cron jobs" % len(index["crons"]))

    # ── Security Groups ────────────────────────────────────────
    print("\n[3/4] Indexing PlasticOS security groups...")
    groups = env["res.groups"].search([
        ("name", "ilike", "plasticos"),
    ])
    for group in groups:
        index["groups"].append({
            "name": group.name,
            "id": group.id,
            "users_count": len(group.users),
        })
        print("  %s (%d users)" % (group.name, len(group.users)))
    print("  Total: %d groups" % len(index["groups"]))

    # ── Custom Fields (x_ prefix) ─────────────────────────────
    print("\n[4/4] Indexing custom fields (x_ prefix)...")
    for model_entry in index["models"]:
        model_name = model_entry["model"]
        if model_name in env:
            model_obj = env[model_name]
            for fname, fobj in model_obj._fields.items():
                if fname.startswith("x_"):
                    index["custom_fields"].append({
                        "model": model_name,
                        "field": fname,
                        "type": fobj.type,
                        "string": fobj.string,
                    })
    print("  Total: %d custom fields" % len(index["custom_fields"]))

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("INDEX SUMMARY")
    print("=" * 60)
    print("  Models:        %d" % len(index["models"]))
    print("  Cron Jobs:     %d" % len(index["crons"]))
    print("  Groups:        %d" % len(index["groups"]))
    print("  Custom Fields: %d" % len(index["custom_fields"]))

    return index

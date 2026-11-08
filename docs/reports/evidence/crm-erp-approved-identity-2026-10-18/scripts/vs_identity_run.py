"""Odoo shell script: run with `odoo shell -d <clone> --no-http < this file`."""

import csv
import json
from collections import Counter

from odoo.addons.plasticos_crm_sync.services.approved_identity import xmlid_name
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator, _new_outcomes

env = globals().get("env")

CSV = "/mnt/extra-addons/Current Work - IGNORE/10-17-26/PlasticOS_CRM_ERP_Identity_GMP_STAGING_2/03_APPROVED_CONTACT_CROSSWALK.csv"
with open(CSV, newline="", encoding="utf-8-sig") as fh:
    rows = list(csv.DictReader(fh))
vs_to_ct = {r["vanillasoft_contact_id"].strip(): r["erp_ct_id"].strip() for r in rows}

Partner = env["res.partner"].with_context(active_test=False)
IMD = env["ir.model.data"]


def person(ct):
    rec = IMD.search(
        [("module", "=", "plasticos_transaction"), ("name", "=", xmlid_name(ct)), ("model", "=", "res.partner")]
    )
    return Partner.browse(rec.res_id) if len(rec) == 1 else Partner.browse()


def counts():
    return {
        "partners": Partner.search_count([]),
        "leads": env["crm.lead"].with_context(active_test=False).search_count([]),
        "phone_lines": env["plasticos.partner.phone"].search_count([]),
        "person_refs": env["plasticos.crm.external.ref"].search_count([("res_model", "=", "res.partner")]),
        "call_events": env["plasticos.crm.call.event"].search_count([]),
        "table_rows": env["plasticos.crm.external.table.row"].search_count([]),
    }


before_counts = counts()
before_fields = {}
for ct in set(vs_to_ct.values()):
    p = person(ct)
    if p:
        before_fields[ct] = (p.id, p.phone or "", p.mobile or "", p.comment or "", len(p.phone_line_ids))

connection = env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()
orch = SyncOrchestrator(env)
orch.outcomes = _new_outcomes()
per_contact = Counter()
reasons = Counter()
exceptions = []
for vs_id in sorted(vs_to_ct):
    try:
        with env.cr.savepoint():
            orch.upsert_contact_external_id(connection, vs_id)
        per_contact[orch.last_lead_outcome or "none"] += 1
    except Exception as exc:  # noqa: BLE001
        per_contact["exception"] += 1
        exceptions.append((vs_id, type(exc).__name__, str(exc)[:160]))
env.cr.commit()

for row in getattr(orch, "error_rows", []) or []:
    reasons[str(row.get("message", ""))[:90]] += 1

after_counts = counts()
changed_fields = []
phone_lines_added = 0
for ct, (pid, phone, mobile, comment, nlines) in before_fields.items():
    p = Partner.browse(pid)
    if (p.phone or "", p.mobile or "", p.comment or "") != (phone, mobile, comment):
        changed_fields.append(ct)
    phone_lines_added += len(p.phone_line_ids) - nlines

refs = env["plasticos.crm.external.ref"].search([("provider", "=", "vanillasoft"), ("res_model", "=", "res.partner")])
ref_by_vs = {r.external_id: r.res_id for r in refs}
bound_right = sum(1 for vs, ct in vs_to_ct.items() if ct in before_fields and ref_by_vs.get(vs) == before_fields[ct][0])
bound_wrong = sum(
    1
    for vs, ct in vs_to_ct.items()
    if vs in ref_by_vs and (ct not in before_fields or ref_by_vs[vs] != before_fields[ct][0])
)
approved_leads = (
    env["crm.lead"].with_context(active_test=False).search_count([("vanillasoft_id", "in", list(vs_to_ct))])
)

print(
    "RESULT "
    + json.dumps(
        {
            "approved_vs_ids": len(vs_to_ct),
            "approved_ct_ids": len(set(vs_to_ct.values())),
            "ct_ids_with_erp_person": len(before_fields),
            "vs_ids_with_erp_person": sum(1 for ct in vs_to_ct.values() if ct in before_fields),
            "outcomes_per_contact": dict(per_contact),
            "orchestrator_outcomes": dict(orch.outcomes),
            "top_reasons": reasons.most_common(8),
            "exceptions": exceptions[:8],
            "exception_count": len(exceptions),
            "before": before_counts,
            "after": after_counts,
            "bound_to_crosswalk_person": bound_right,
            "bound_to_other_partner": bound_wrong,
            "new_leads_for_approved_ids": approved_leads,
            "phone_mobile_comment_changed": len(changed_fields),
            "phone_lines_added_on_approved_people": phone_lines_added,
        },
        indent=1,
        default=str,
    )
)

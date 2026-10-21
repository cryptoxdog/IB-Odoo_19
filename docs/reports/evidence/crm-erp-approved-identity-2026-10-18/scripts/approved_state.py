"""Odoo shell script: print the database state of every approved contact as one JSON line. No API calls."""

import csv
import json

from odoo.addons.plasticos_crm_sync.services.approved_identity import xmlid_name

env = globals().get("env")

CSV = "/mnt/extra-addons/Current Work - IGNORE/10-17-26/PlasticOS_CRM_ERP_Identity_GMP_STAGING_2/03_APPROVED_CONTACT_CROSSWALK.csv"
with open(CSV, newline="", encoding="utf-8-sig") as fh:
    vs_to_ct = {r["vanillasoft_contact_id"].strip(): r["erp_ct_id"].strip() for r in csv.DictReader(fh)}

IMD = env["ir.model.data"]
Partner = env["res.partner"].with_context(active_test=False)
Ref = env["plasticos.crm.external.ref"]
Call = env["plasticos.crm.call.event"]


def iso(value):
    return value.isoformat() if value else None


persons = {}
for ct in sorted(set(vs_to_ct.values())):
    marker = IMD.search(
        [("module", "=", "plasticos_transaction"), ("name", "=", xmlid_name(ct)), ("model", "=", "res.partner")]
    )
    if len(marker) != 1:
        persons[ct] = {"marker_rows": len(marker)}
        continue
    p = Partner.browse(marker.res_id)
    persons[ct] = {
        "marker_rows": 1,
        "partner_id": p.id,
        "exists": bool(p.exists()),
        "name": p.name or "",
        "parent_id": p.parent_id.id or None,
        "is_company": p.is_company,
        "active": p.active,
        "email": p.email or "",
        "phone": p.phone or "",
        "mobile": p.mobile or "",
        "comment": p.comment or "",
        "write_date": iso(p.write_date),
        "phone_lines": sorted(
            [line.id, line.label or "", line.number or "", iso(line.write_date)] for line in p.phone_line_ids
        ),
    }

contacts = {}
for vs, ct in sorted(vs_to_ct.items()):
    refs = Ref.search([("provider", "=", "vanillasoft"), ("external_id", "=", vs)])
    calls = Call.search([("provider", "=", "vanillasoft"), ("contact_external_id", "=", vs)])
    contacts[vs] = {
        "ct_id": ct,
        "refs": sorted([r.id, r.res_model, r.res_id, r.lead_id.id or None] for r in refs),
        "calls": sorted(
            [c.id, c.external_id, c.lead_id.id or None, iso(c.call_datetime_utc), c.comment or ""] for c in calls
        ),
    }

counts = {
    "partners": Partner.search_count([]),
    "leads": env["crm.lead"].with_context(active_test=False).search_count([]),
    "phone_lines": env["plasticos.partner.phone"].search_count([]),
    "person_refs": Ref.search_count([("res_model", "=", "res.partner")]),
    "call_events": Call.search_count([]),
    "table_rows": env["plasticos.crm.external.table.row"].search_count([]),
    "erp_partner_markers": IMD.search_count([("module", "=", "plasticos_transaction"), ("model", "=", "res.partner")]),
}
print("STATE " + json.dumps({"counts": counts, "persons": persons, "contacts": contacts}, sort_keys=True))

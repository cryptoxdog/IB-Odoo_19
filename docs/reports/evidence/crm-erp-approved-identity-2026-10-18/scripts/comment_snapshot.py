"""Odoo shell script: print every crosswalk person's comment as one JSON line."""

import csv
import json

from odoo.addons.plasticos_crm_sync.services.approved_identity import xmlid_name

env = globals().get("env")

CSV = "/mnt/extra-addons/Current Work - IGNORE/10-17-26/PlasticOS_CRM_ERP_Identity_GMP_STAGING_2/03_APPROVED_CONTACT_CROSSWALK.csv"
with open(CSV, newline="", encoding="utf-8-sig") as fh:
    cts = sorted({r["erp_ct_id"].strip() for r in csv.DictReader(fh)})
IMD = env["ir.model.data"]
Partner = env["res.partner"].with_context(active_test=False)
out = {}
for ct in cts:
    rec = IMD.search(
        [("module", "=", "plasticos_transaction"), ("name", "=", xmlid_name(ct)), ("model", "=", "res.partner")]
    )
    if len(rec) == 1:
        p = Partner.browse(rec.res_id)
        out[ct] = {"partner_id": p.id, "comment": p.comment or "", "phone": p.phone or "", "mobile": p.mobile or ""}
print("SNAPSHOT " + json.dumps(out))

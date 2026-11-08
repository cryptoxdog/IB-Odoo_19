"""Odoo shell script: run with `odoo shell -d <clone> --no-http < this file`."""

import csv
import json

from odoo.addons.plasticos_crm_sync.services.approved_identity import xmlid_name
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator, _new_outcomes

env = globals().get("env")

CSV = "/mnt/extra-addons/Current Work - IGNORE/10-17-26/PlasticOS_CRM_ERP_Identity_GMP_STAGING_2/03_APPROVED_CONTACT_CROSSWALK.csv"
with open(CSV, newline="", encoding="utf-8-sig") as fh:
    vs_to_ct = {r["vanillasoft_contact_id"].strip(): r["erp_ct_id"].strip() for r in csv.DictReader(fh)}

Ref = env["plasticos.crm.external.ref"]
bound = {
    r.external_id: r.res_id for r in Ref.search([("provider", "=", "vanillasoft"), ("res_model", "=", "res.partner")])
}
IMD = env["ir.model.data"]

connection = env["plasticos.crm.connection"].search([("provider", "=", "vanillasoft")], limit=1)
orch = SyncOrchestrator(env)
orch.outcomes = _new_outcomes()
orch._load_approved_crosswalk()
adapter = orch._build_adapter(connection)

out = []
for vs_id in sorted(vs_to_ct, key=int):
    ct = vs_to_ct[vs_id]
    marker = IMD.search(
        [("module", "=", "plasticos_transaction"), ("name", "=", xmlid_name(ct)), ("model", "=", "res.partner")]
    )
    if vs_id in bound:
        out.append({"vs_id": vs_id, "ct_id": ct, "status": "bound", "partner_id": bound[vs_id]})
        continue
    dto = adapter.get_contact(vs_id)
    before = len(getattr(orch, "error_rows", []) or [])
    try:
        with env.cr.savepoint():
            orch._upsert_lead(connection, dto, adapter)
    except Exception as exc:  # noqa: BLE001
        orch.error_rows.append({"message": f"exception {type(exc).__name__}: {exc}"})
    msgs = [str(r.get("message", "")) for r in (orch.error_rows or [])[before:]]
    out.append(
        {
            "vs_id": vs_id,
            "ct_id": ct,
            "status": orch.last_lead_outcome or "none",
            "erp_marker_rows": len(marker),
            "erp_partner_id": marker.res_id if len(marker) == 1 else "",
            "contact_note_present": bool(dto.contact_note),
            "contact_note_chars": len(dto.contact_note or ""),
            "crm_phone_numbers": len(set(dto.phone_numbers or ()) | {n for n in (dto.phone, dto.mobile) if n}),
            "existing_lead_for_vs_id": env["crm.lead"]
            .with_context(active_test=False)
            .search_count([("vanillasoft_id", "=", vs_id)]),
            "provider_table_rows": env["plasticos.crm.external.table.row"].search_count(
                [("contact_external_id", "=", vs_id)]
            ),
            "reason": " | ".join(msgs),
        }
    )
env.cr.rollback()
print("DETAIL " + json.dumps(out))

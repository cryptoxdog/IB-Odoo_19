"""#303 head only. Persist an undated bill beside a dated historical invoice, then stop."""

import json

existing = env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")])
existing.write({"active": False})
partner = env["res.partner"].create({"name": "Probe atomic partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1})
tag = env["plasticos.document.tag"].create({"name": "Probe atomic", "code": "probe_gate_atomic"})
rule = env["plasticos.document.rule"].create(
    {
        "name": "Probe atomic",
        "tag_id": tag.id,
        "res_model": "plasticos.transaction",
        "required_for_invoice": True,
        "required_for_close": True,
    }
)
invoice = env["account.move"].create(
    {
        "move_type": "out_invoice",
        "partner_id": partner.id,
        "invoice_origin": "54839",
        "ref": "54839",
        "invoice_date": "2022-04-01",
        "invoice_line_ids": [(0, 0, {"name": "Historical invoice", "quantity": 1, "price_unit": 50.0, "is_imported": True})],
    }
)
bill = env["account.move"].create(
    {
        "move_type": "in_invoice",
        "partner_id": partner.id,
        "invoice_origin": "54839",
        "ref": "V-7275",
        "invoice_line_ids": [(0, 0, {"name": "Undated bill", "quantity": 1, "price_unit": 40.0, "is_imported": True})],
    }
)
env["ir.model.data"].create(
    [
        {
            "module": "plasticos_transaction",
            "name": "legacy_erp_outinv_atomic",
            "model": "account.move",
            "res_id": invoice.id,
            "noupdate": True,
        },
        {
            "module": "plasticos_transaction",
            "name": "legacy_erp_ininv_atomic",
            "model": "account.move",
            "res_id": bill.id,
            "noupdate": True,
        },
    ]
)
tx = env["plasticos.transaction"].create(
    {
        "name": "ATOMIC-54839",
        "buyer_id": partner.id,
        "supplier_id": partner.id,
        "customer_invoice_id": invoice.id,
        "vendor_bill_ids": [(4, bill.id)],
    }
)
print(
    "SETUP "
    + json.dumps(
        {
            "tx_id": tx.id,
            "tx_name": tx.name,
            "compliance": tx.compliance_status,
            "invoice_id": invoice.id,
            "invoice_state": invoice.state,
            "invoice_date": str(invoice.invoice_date or ""),
            "bill_id": bill.id,
            "bill_state": bill.state,
            "bill_date": str(bill.invoice_date or ""),
            "tag_id": tag.id,
            "rule_id": rule.id,
            "partner_id": partner.id,
            "rules_deactivated": len(existing),
        }
    )
)
env.cr.commit()

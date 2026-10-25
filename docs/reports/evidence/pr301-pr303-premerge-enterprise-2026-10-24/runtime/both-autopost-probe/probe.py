"""Disposable clone probe. Prints one GAP_PROBE line. Rolls back."""

import base64
import json

from odoo.exceptions import UserError

existing = env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")])
existing.write({"active": False})
partner = env["res.partner"].create({"name": "Gap probe partner", "is_company": True})
tag = env["plasticos.document.tag"].create({"name": "Gap probe", "code": "gap_probe_autopost"})
env["plasticos.document.rule"].create(
    {
        "name": "Gap probe rule",
        "tag_id": tag.id,
        "res_model": "plasticos.transaction",
        "required_for_invoice": True,
        "required_for_close": True,
    }
)
tx = env["plasticos.transaction"].create({"supplier_id": partner.id, "buyer_id": partner.id})
move = env["account.move"].create(
    {
        "move_type": "out_invoice",
        "partner_id": partner.id,
        "invoice_line_ids": [(0, 0, {"name": "Line", "quantity": 1, "price_unit": 50.0})],
    }
)
bill = env["account.move"].create(
    {
        "move_type": "in_invoice",
        "partner_id": partner.id,
        "invoice_line_ids": [(0, 0, {"name": "Line", "quantity": 1, "price_unit": 50.0})],
    }
)
tx.write({"customer_invoice_id": move.id, "vendor_bill_ids": [(4, bill.id)]})
service = env["plasticos.compliance.service"]
before = {
    "compliance": tx.compliance_status,
    "invoice_state": move.state,
    "bill_state": bill.state,
    "invoice_origin": move.invoice_origin or "",
    "bill_origin": bill.invoice_origin or "",
    "missing": service.get_missing_documents("plasticos.transaction", tx.id),
    "rules_deactivated": len(existing),
}
attachment = env["ir.attachment"].create(
    {
        "name": "gap.txt",
        "datas": base64.b64encode(b"gap"),
        "res_model": "plasticos.document",
        "res_id": 0,
    }
)
error = None
try:
    env["plasticos.document"].create(
        {
            "name": "Gap probe doc",
            "tag_id": tag.id,
            "res_model": "plasticos.transaction",
            "res_id": tx.id,
            "transaction_id": tx.id,
            "attachment_id": attachment.id,
            "verified": True,
        }
    )
except UserError as exc:
    error = str(exc)
tx.invalidate_recordset()
move.invalidate_recordset()
bill.invalidate_recordset()
print(
    "GAP_PROBE "
    + json.dumps(
        {
            "before_document": before,
            "after_document": {
                "compliance": tx.compliance_status,
                "invoice_state": move.state,
                "bill_state": bill.state,
                "missing": service.get_missing_documents("plasticos.transaction", tx.id),
                "error": error,
            },
        }
    )
)
env.cr.rollback()

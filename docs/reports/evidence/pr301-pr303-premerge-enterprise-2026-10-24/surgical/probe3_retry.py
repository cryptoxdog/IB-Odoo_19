"""#303 head only. Date the persisted bill, then satisfy the rule again."""

import base64
import json

tx = env["plasticos.transaction"].search([("name", "=", "ATOMIC-54839")], limit=1)
tag = env["plasticos.document.tag"].search([("code", "=", "probe_gate_atomic")], limit=1)
invoice = tx.customer_invoice_id
bill = tx.vendor_bill_ids[:1]
before = {
    "compliance": tx.compliance_status,
    "invoice_state": invoice.state,
    "bill_state": bill.state,
    "bill_date": str(bill.invoice_date or ""),
    "documents": env["plasticos.document"].search_count([("res_model", "=", "plasticos.transaction"), ("res_id", "=", tx.id)]),
}
bill.write({"invoice_date": "2022-03-15", "invoice_date_due": "2022-03-20"})
attachment = env["ir.attachment"].create(
    {
        "name": "atomic-retry.txt",
        "datas": base64.b64encode(b"retry"),
        "res_model": "plasticos.document",
        "res_id": 0,
    }
)
error = None
try:
    env["plasticos.document"].create(
        {
            "name": "Atomic retry doc",
            "tag_id": tag.id,
            "res_model": "plasticos.transaction",
            "res_id": tx.id,
            "transaction_id": tx.id,
            "attachment_id": attachment.id,
            "verified": True,
        }
    )
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
tx.invalidate_recordset()
invoice.invalidate_recordset()
bill.invalidate_recordset()
print(
    "RETRY "
    + json.dumps(
        {
            "before_dating_the_bill": before,
            "after": {
                "compliance": tx.compliance_status,
                "invoice_state": invoice.state,
                "bill_state": bill.state,
                "bill_date": str(bill.invoice_date or ""),
                "documents": env["plasticos.document"].search_count(
                    [("res_model", "=", "plasticos.transaction"), ("res_id", "=", tx.id)]
                ),
                "error": error,
            },
        }
    )
)
env.cr.commit()

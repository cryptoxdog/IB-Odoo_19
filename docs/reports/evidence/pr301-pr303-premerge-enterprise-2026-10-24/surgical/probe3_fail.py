"""#303 head only. Satisfy the rule and let the posting error abort this transaction."""

import base64

tx = env["plasticos.transaction"].search([("name", "=", "ATOMIC-54839")], limit=1)
tag = env["plasticos.document.tag"].search([("code", "=", "probe_gate_atomic")], limit=1)
attachment = env["ir.attachment"].create(
    {
        "name": "atomic.txt",
        "datas": base64.b64encode(b"atomic"),
        "res_model": "plasticos.document",
        "res_id": 0,
    }
)
env["plasticos.document"].create(
    {
        "name": "Atomic doc",
        "tag_id": tag.id,
        "res_model": "plasticos.transaction",
        "res_id": tx.id,
        "transaction_id": tx.id,
        "attachment_id": attachment.id,
        "verified": True,
    }
)
print("FAIL_UNEXPECTED_SUCCESS")
env.cr.commit()

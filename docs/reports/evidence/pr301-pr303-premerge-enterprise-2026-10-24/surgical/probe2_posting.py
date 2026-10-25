"""#303 head only. Historical versus operational through missing -> compliant. Rolls back."""

import base64
import json

trace = []
move_cls = type(env["account.move"])
tx_cls = type(env["plasticos.transaction"])
service_cls = type(env["plasticos.compliance.service"])
original_post = move_cls.action_post
original_auto = tx_cls._auto_post_pending_invoices
original_is = service_cls.is_compliant


def wrapped_is(self, res_model, res_id, purpose=None):
    result = original_is(self, res_model, res_id, purpose=purpose)
    trace.append(
        {
            "where": "plasticos.compliance.service.is_compliant",
            "res_id": res_id,
            "purpose": purpose,
            "result": result,
        }
    )
    return result


def wrapped_auto(self):
    trace.append(
        {
            "where": "plasticos.transaction._auto_post_pending_invoices",
            "tx": self.name,
            "tx_state": self.state,
            "compliance_before_post": self.compliance_status,
            "customer_invoice": self.customer_invoice_id.id,
            "vendor_bills": self.vendor_bill_ids.ids,
        }
    )
    return original_auto(self)


def wrapped_post(self):
    trace.append(
        {
            "where": "account.move.action_post",
            "moves": [
                {"id": move.id, "type": move.move_type, "origin": move.invoice_origin or "", "state": move.state}
                for move in self
            ],
        }
    )
    return original_post(self)


service_cls.is_compliant = wrapped_is
tx_cls._auto_post_pending_invoices = wrapped_auto
move_cls.action_post = wrapped_post

existing = env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")])
existing.write({"active": False})
partner = env["res.partner"].create({"name": "Probe partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1})
product = env["product.product"].search([("sale_ok", "=", True)], limit=1)
tag = env["plasticos.document.tag"].create({"name": "Probe gate", "code": "probe_gate_post"})
env["plasticos.document.rule"].create(
    {
        "name": "Probe gate",
        "tag_id": tag.id,
        "res_model": "plasticos.transaction",
        "required_for_invoice": True,
        "required_for_close": True,
    }
)


def stamp(move, xml_name):
    env["ir.model.data"].create(
        {
            "module": "plasticos_transaction",
            "name": xml_name,
            "model": "account.move",
            "res_id": move.id,
            "noupdate": True,
        }
    )


def line_vals(name):
    return {
        "name": name,
        "quantity": 1,
        "price_unit": 50.0,
        "is_imported": True,
    }


def satisfy(tx):
    attachment = env["ir.attachment"].create(
        {
            "name": "probe.txt",
            "datas": base64.b64encode(b"probe"),
            "res_model": "plasticos.document",
            "res_id": 0,
        }
    )
    env["plasticos.document"].create(
        {
            "name": f"Probe doc {tx.name}",
            "tag_id": tag.id,
            "res_model": "plasticos.transaction",
            "res_id": tx.id,
            "transaction_id": tx.id,
            "attachment_id": attachment.id,
            "verified": True,
        }
    )


sale = env["sale.order"].create(
    {
        "name": "14263",
        "origin": "54839",
        "partner_id": partner.id,
        "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1, "price_unit": 50.0})],
    }
)
historical_invoice = env["account.move"].create(
    {
        "move_type": "out_invoice",
        "partner_id": partner.id,
        "invoice_origin": "54839",
        "ref": "54839",
        "invoice_date": "2022-04-01",
        "invoice_line_ids": [(0, 0, line_vals("Historical invoice"))],
    }
)
historical_bill = env["account.move"].create(
    {
        "move_type": "in_invoice",
        "partner_id": partner.id,
        "invoice_origin": "54839",
        "ref": "V-7275",
        "invoice_date": "2022-03-15",
        "invoice_date_due": "2022-03-20",
        "invoice_line_ids": [(0, 0, line_vals("Historical bill"))],
    }
)
stamp(historical_invoice, "legacy_erp_outinv_54839")
stamp(historical_bill, "legacy_erp_ininv_591398")
historical_tx = env["plasticos.transaction"].create(
    {
        "name": "54839",
        "state": "closed",
        "buyer_id": partner.id,
        "supplier_id": partner.id,
        "sale_order_id": sale.id,
        "customer_invoice_id": historical_invoice.id,
        "vendor_bill_ids": [(4, historical_bill.id)],
    }
)
sale.transaction_id = historical_tx.id
before_historical = historical_tx.compliance_status
satisfy(historical_tx)

live_sale = env["sale.order"].create(
    {
        "partner_id": partner.id,
        "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1, "price_unit": 80.0})],
    }
)
live_sale.action_confirm()
operational = live_sale._create_invoices()
operational.write({"invoice_date": "2026-10-24"})
live_tx = live_sale.transaction_id
live_tx.write({"customer_invoice_id": operational.id})
before_live = live_tx.compliance_status
satisfy(live_tx)

historical_tx.invalidate_recordset()
historical_invoice.invalidate_recordset()
historical_bill.invalidate_recordset()
live_tx.invalidate_recordset()
operational.invalidate_recordset()
print(
    "POSTING "
    + json.dumps(
        {
            "head": "190c497bdea1362cad87e231c713efdcd25240d4",
            "rules_deactivated": len(existing),
            "historical": {
                "tx_state": historical_tx.state,
                "compliance_before": before_historical,
                "compliance_after": historical_tx.compliance_status,
                "sale_name": sale.name,
                "sale_origin": sale.origin,
                "invoice_origin": historical_invoice.invoice_origin,
                "invoice_state": historical_invoice.state,
                "bill_origin": historical_bill.invoice_origin,
                "bill_state": historical_bill.state,
            },
            "operational": {
                "tx_name": live_tx.name,
                "tx_state": live_tx.state,
                "compliance_before": before_live,
                "compliance_after": live_tx.compliance_status,
                "sale_name": live_sale.name,
                "sale_origin": live_sale.origin or "",
                "invoice_origin": operational.invoice_origin or "",
                "invoice_state": operational.state,
                "line_is_imported": operational.invoice_line_ids[:1].is_imported,
                "sale_line_linked": bool(operational.invoice_line_ids.sale_line_ids),
            },
            "trace": trace,
        },
        default=str,
    )
)
env.cr.rollback()

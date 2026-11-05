from odoo import api, fields, models
from odoo.exceptions import UserError


class PlasticosIntakeTxBridge(models.Model):
    """Adds transaction reverse navigation to intake."""

    _inherit = "plasticos.intake"

    transaction_ids = fields.One2many(
        "plasticos.transaction",
        "intake_id",
        string="Transactions",
    )
    transaction_count = fields.Integer(
        compute="_compute_transaction_count",
        string="Transaction Count",
    )

    @api.depends("transaction_ids")
    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)

    def action_view_transactions(self):
        """View transactions created from this intake."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": f"Transactions — {self.name}",
            "res_model": "plasticos.transaction",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
        }
        if self.transaction_count == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.transaction_ids.id,
                }
            )
        return action

    def action_make_po(self):
        """Create transaction from intake and close as Won."""
        self.ensure_one()
        self._assert_status("offer_sent", "processing", "matched")

        if not self.partner_id:
            raise UserError("Cannot create PO without a supplier partner.")

        tx_vals = {
            "intake_id": self.id,
            "supplier_id": self.partner_id.id,
            "quantity": self.quantity_per_load_lbs,
        }

        if self.material_profile_id:
            tx_vals["supplier_profile_id"] = self.material_profile_id.id

        selected_match = self.match_line_ids.filtered("selected").sorted("match_score", reverse=True)[:1]
        if selected_match:
            buyer = self.env["res.partner"].search([("name", "=", selected_match.buyer_name)], limit=1)
            if buyer:
                tx_vals["buyer_id"] = buyer.id

        tx = self.env["plasticos.transaction"].create(tx_vals)

        self.status = "won"
        self.message_post(
            body=(
                "PO created → Transaction "
                f'<a href="#" data-oe-model="plasticos.transaction" data-oe-id="{tx.id}">{tx.name or tx.id}</a>'
            )
        )

        return {
            "type": "ir.actions.act_window",
            "name": f"Transaction — {self.name}",
            "res_model": "plasticos.transaction",
            "res_id": tx.id,
            "view_mode": "form",
            "target": "current",
        }

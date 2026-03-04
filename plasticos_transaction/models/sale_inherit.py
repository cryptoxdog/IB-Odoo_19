from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transaction_id = fields.Many2one("plasticos.transaction")

    def action_confirm(self):
        """Confirm sale order and auto-create linked transaction.

        MRO Note: If plasticos_automation is installed, its action_confirm() runs first
        (checking approval), then calls super() which reaches here.
        This ensures transaction creation only happens if approval passes.

        NOTE: We do NOT pass 'name' to transaction.create() — the ir.sequence
        in plasticos.transaction.create() generates the proper TX-XXXXX reference.
        The SO reference is stored via sale_order_id for traceability.
        """
        res = super().action_confirm()

        for rec in self:
            if not rec.transaction_id:
                transaction = self.env["plasticos.transaction"].create({"sale_order_id": rec.id})
                rec.transaction_id = transaction.id
                transaction.action_activate()

        return res

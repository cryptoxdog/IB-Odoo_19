from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transaction_id = fields.Many2one("plasticos.transaction", ondelete="cascade")

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

        # Batch create transactions for SOs without one
        recs_needing_tx = self.filtered(lambda r: not r.transaction_id)
        if recs_needing_tx:
            vals_list = [{"sale_order_id": rec.id} for rec in recs_needing_tx]
            transactions = self.env["plasticos.transaction"].create(vals_list)
            for rec, tx in zip(recs_needing_tx, transactions):
                rec.transaction_id = tx.id
                tx.action_activate()

        return res

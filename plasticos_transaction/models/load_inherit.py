from odoo import models


class PlasticosLoad(models.Model):
    _inherit = "plasticos.load"

    # Link owned by transaction (transaction.load_id). No duplicate FK on load.

    def write(self, vals):
        res = super().write(vals)

        if "state" in vals and vals["state"] == "closed":
            for rec in self:
                tx = self.env["plasticos.transaction"].search([("load_id", "=", rec.id)], limit=1)
                if tx:
                    tx.message_post(body="Logistics closed.")

        return res

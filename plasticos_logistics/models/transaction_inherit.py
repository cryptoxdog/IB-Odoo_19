from odoo import api, fields, models


class PlasticosTransactionLoadBridge(models.Model):
    """A transaction owns zero or more loads. The stored parent is on the load."""

    _inherit = "plasticos.transaction"

    load_ids = fields.One2many(
        "plasticos.load",
        "transaction_id",
        string="Loads",
        help="Logistics loads whose stored parent is this transaction.",
    )
    load_count = fields.Integer(compute="_compute_load_count")

    @api.depends("load_ids")
    def _compute_load_count(self):
        for rec in self:
            rec.load_count = len(rec.load_ids)

    def action_view_loads(self):
        """Open this transaction's loads. An empty set stays an empty set."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Loads",
            "res_model": "plasticos.load",
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.id)],
            "context": {"default_transaction_id": self.id},
        }
        if len(self.load_ids) == 1:
            action["view_mode"] = "form"
            action["res_id"] = self.load_ids.id
        return action

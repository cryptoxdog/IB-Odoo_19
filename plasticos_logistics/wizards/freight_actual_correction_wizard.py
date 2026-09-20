"""Attributed correction entry point for immutable freight calibration evidence."""

from odoo import fields, models
from odoo.exceptions import ValidationError


class PlasticosFreightActualCorrectionWizard(models.TransientModel):
    _name = "plasticos.freight.actual.correction.wizard"
    _description = "Plasticos Freight Actual Cost Correction"

    load_id = fields.Many2one("plasticos.load", required=True, readonly=True, ondelete="cascade")
    actual_cost = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", required=True, ondelete="restrict")
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        if self.actual_cost < 0:
            raise ValidationError("Actual freight cost cannot be negative.")
        if not self.reason.strip():
            raise ValidationError("A correction reason is required.")
        self.load_id.action_correct_actual_freight_cost(self.actual_cost, self.currency_id, self.reason.strip())
        return {"type": "ir.actions.act_window_close"}

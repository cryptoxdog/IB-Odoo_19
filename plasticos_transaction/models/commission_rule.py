from odoo import api, models
from odoo.exceptions import ValidationError


class PlasticosCommissionRuleInherit(models.Model):
    """Extend commission rule with transaction-specific constraints.

    The base model is defined in plasticos_commission. This module adds
    the unique active sales rep constraint.
    """

    _inherit = "plasticos.commission.rule"

    @api.constrains("sales_rep_id", "active")
    def _check_unique_active_sales_rep(self):
        """Ensure only one active commission rule per sales rep.

        NOTE: This is a Python constraint, not SQL, because SQL unique constraints
        don't respect Odoo's active field filtering. A SQL constraint would block
        creating a new rule even if the old one is archived.
        """
        for rec in self:
            if not rec.active:
                continue
            duplicate = self.search(
                [
                    ("sales_rep_id", "=", rec.sales_rep_id.id),
                    ("active", "=", True),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(f"Sales rep {rec.sales_rep_id.name} already has an active commission rule.")

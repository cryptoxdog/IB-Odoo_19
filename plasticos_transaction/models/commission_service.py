from odoo import models


class PlasticosCommissionService(models.AbstractModel):
    _name = "plasticos.commission.service"
    _description = "Commission Service"

    def compute_commission(self, transaction):
        """Compute commission for a transaction.

        Priority:
        1. Admin override (commission_override_pct) if > 0
        2. Commission rule percentage
        3. Zero if neither set
        """
        # Admin override takes precedence
        if transaction.commission_override_pct and transaction.commission_override_pct > 0:
            return transaction.gross_margin * transaction.commission_override_pct

        # Standard rule-based commission
        if transaction.commission_rule_id:
            return transaction.gross_margin * transaction.commission_rule_id.percentage

        return 0.0

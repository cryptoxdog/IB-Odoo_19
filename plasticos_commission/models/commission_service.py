from odoo import models


class PlasticosCommissionService(models.AbstractModel):
    """Commission calculation service.

    AbstractModel pattern: provides compute_commission() method that can be
    called from any model via self.env["plasticos.commission.service"].

    Commission is calculated as:
        gross_margin * commission_rate

    Where commission_rate comes from:
        1. commission_override_pct (if set on transaction)
        2. commission_rule_id.percentage (if rule assigned)
        3. 0.0 (no commission)
    """

    _name = "plasticos.commission.service"
    _description = "Commission Calculation Service"

    def compute_commission(self, transaction):
        """Compute commission amount for a transaction.

        Args:
            transaction: plasticos.transaction record

        Returns:
            float: Commission amount (gross_margin * rate)
        """
        if not transaction:
            return 0.0

        gross_margin = transaction.gross_margin or 0.0

        # Priority 1: Manual override percentage
        if transaction.commission_override_pct:
            return gross_margin * transaction.commission_override_pct

        # Priority 2: Commission rule
        if transaction.commission_rule_id:
            return gross_margin * transaction.commission_rule_id.percentage

        # No commission configured
        return 0.0

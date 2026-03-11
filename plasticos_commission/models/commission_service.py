from odoo import models


class PlasticosCommissionService(models.AbstractModel):
    """Commission calculation service interface.

    AbstractModel pattern: provides compute_commission() method that can be
    called from any model via self.env["plasticos.commission.service"].

    This base class defines the interface. The actual implementation is
    provided by plasticos_transaction which inherits and overrides
    compute_commission() with transaction-specific logic.

    Commission is calculated as:
        gross_margin * commission_rate

    Where commission_rate comes from (in plasticos_transaction):
        1. commission_override_pct (if set on transaction)
        2. commission_rule_id.percentage (if rule assigned)
        3. 0.0 (no commission)
    """

    _name = "plasticos.commission.service"
    _description = "Commission Calculation Service"

    def compute_commission(self, record):
        """Compute commission amount for a record.

        Args:
            record: Record with commission-related fields (e.g., plasticos.transaction)

        Returns:
            float: Commission amount

        Note:
            This base implementation returns 0.0. The plasticos_transaction module
            overrides this with transaction-specific logic.
        """
        return 0.0

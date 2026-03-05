from odoo import models


class PlasticosCommissionServiceInherit(models.AbstractModel):
    """Extend commission service with transaction-specific logic.

    The base service is defined in plasticos_commission. This module overrides
    compute_commission to add the > 0 check for override percentage.

    NOTE: AbstractModel = no database table, no ACL needed.
    """

    _inherit = "plasticos.commission.service"

    def compute_commission(self, transaction):
        """Compute commission for a transaction.

        Priority:
        1. Admin override (commission_override_pct) if > 0
        2. Commission rule percentage
        3. Zero if neither set

        Override: Adds explicit > 0 check for override percentage.
        """
        if not transaction:
            return 0.0

        gross_margin = transaction.gross_margin or 0.0

        # Admin override takes precedence (must be > 0)
        if transaction.commission_override_pct and transaction.commission_override_pct > 0:
            return gross_margin * transaction.commission_override_pct

        # Standard rule-based commission
        if transaction.commission_rule_id:
            return gross_margin * transaction.commission_rule_id.percentage

        return 0.0

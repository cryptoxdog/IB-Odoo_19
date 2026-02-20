from odoo import models


class PlasticosCommissionService(models.AbstractModel):
    _name = "plasticos.commission.service"
    _description = "Commission Service"

    def compute_commission(self, transaction):
        if transaction.commission_rule_id:
            return transaction.gross_margin * transaction.commission_rule_id.percentage
        return 0.0

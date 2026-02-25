from odoo import fields, models


class ShardRebalancePlan(models.Model):
    _name = "plasticos.graph.shard.rebalance.plan"
    _description = "Shard Rebalance Plan"

    source_shard = fields.Char(required=True)
    target_shard = fields.Char(required=True)
    facility_id = fields.Char(required=True)
    executed = fields.Boolean(default=False)

from odoo import fields, models


class ShardMetadata(models.Model):
    _name = "plasticos.graph.shard.metadata"
    _description = "Shard Metadata Registry"

    shard_name = fields.Char(required=True)
    node_count = fields.Integer(default=0)
    relationship_count = fields.Integer(default=0)
    last_health_check = fields.Datetime()

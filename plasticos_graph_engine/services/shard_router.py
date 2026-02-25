import hashlib

from odoo import models


class ShardRouter(models.AbstractModel):
    _name = "plasticos.shard.router"
    _description = "Facility Hash Shard Router"

    SHARD_COUNT = 3
    CONTROL_DB = "graph_control"
    SHARD_PREFIX = "graph_shard_"

    def get_shard_db(self, facility_id):
        shard_id = int(hashlib.sha256(str(facility_id).encode()).hexdigest(), 16) % self.SHARD_COUNT
        return f"{self.SHARD_PREFIX}{shard_id}"

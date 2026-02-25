from odoo import models


class ShardRebalanceService(models.AbstractModel):
    _name = "plasticos.graph.shard.rebalance"
    _description = "Shard Rebalance Service"

    def generate_plan(self):
        metrics = self.env["plasticos.graph.shard.metrics"].collect()
        metrics.sort(key=lambda x: x["nodes"])

        if len(metrics) < 2:
            return

        light = metrics[0]
        heavy = metrics[-1]

        if heavy["nodes"] - light["nodes"] < 1000:
            return

        self.env["plasticos.graph.shard.rebalance.plan"].create(
            {"source_shard": heavy["db"], "target_shard": light["db"], "facility_id": "auto_selected"}
        )

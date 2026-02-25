from odoo import models


class ShardMetricsService(models.AbstractModel):
    _name = "plasticos.graph.shard.metrics"
    _description = "Shard Metrics Service"

    def collect(self):
        router = self.env["plasticos.shard.router"]
        driver = self.env["plasticos.neo4j.cluster.driver"]

        stats = []
        for i in range(router.SHARD_COUNT):
            db = f"{router.SHARD_PREFIX}{i}"
            result = driver.execute_on_db(db, "MATCH (n) RETURN count(n) AS nodes")
            stats.append({"db": db, "nodes": result[0]["nodes"]})
        return stats

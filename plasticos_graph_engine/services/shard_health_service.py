from odoo import models


class ShardHealthService(models.AbstractModel):
    _name = "plasticos.shard.health.service"
    _description = "Shard Health Service"

    def check_all(self):
        router = self.env["plasticos.shard.router"]
        driver = self.env["plasticos.neo4j.cluster.driver"]

        for i in range(router.SHARD_COUNT):
            db = f"{router.SHARD_PREFIX}{i}"
            result = driver.execute_on_db(db, "MATCH (n) RETURN count(n) AS nodes")
            self.env["plasticos.graph.shard.metadata"].create(
                {
                    "shard_name": db,
                    "node_count": result[0]["nodes"] if result else 0,
                }
            )

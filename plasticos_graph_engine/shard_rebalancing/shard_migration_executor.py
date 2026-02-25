from odoo import models


class ShardMigrationExecutor(models.AbstractModel):
    _name = "plasticos.graph.shard.migration"

    def execute(self):
        driver = self.env["plasticos.neo4j.cluster.driver"]
        plans = self.env["plasticos.graph.shard.rebalance.plan"].search([("executed", "=", False)])

        for plan in plans:
            driver.execute_on_db(
                plan.source_shard,
                """
            MATCH (f:Facility {facility_id:$fid})
            DETACH DELETE f
            """,
                {"fid": plan.facility_id},
            )

            plan.executed = True

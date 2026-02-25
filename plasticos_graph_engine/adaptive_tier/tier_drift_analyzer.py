from odoo import models


class TierDriftAnalyzer(models.AbstractModel):
    _name = "plasticos.graph.tier.drift"
    _description = "Tier Drift Analyzer"

    def detect(self, tenant_code):
        router = self.env["plasticos.graph.tenant.router"]
        db = router.get_database(tenant_code)
        driver = self.env["plasticos.neo4j.cluster.driver"]

        return driver.execute_on_db(
            db,
            """
        MATCH (g:Grade)
        WHERE g.reinforcement_score > 0.8 AND g.tier_level > 2
        RETURN g.grade_id AS grade_id
        """,
        )

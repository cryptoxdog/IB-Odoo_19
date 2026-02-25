from odoo import models


class TierReclassificationEngine(models.AbstractModel):
    _name = "plasticos.graph.tier.reclass"
    _description = "Tier Reclassification Engine"

    def apply(self, tenant_code):
        drift = self.env["plasticos.graph.tier.drift"].detect(tenant_code)
        router = self.env["plasticos.graph.tenant.router"]
        db = router.get_database(tenant_code)
        driver = self.env["plasticos.neo4j.cluster.driver"]

        for row in drift:
            driver.execute_on_db(
                db,
                """
            MATCH (g:Grade {grade_id:$gid})
            SET g.tier_level = g.tier_level - 1
            """,
                {"gid": row["grade_id"]},
            )

from odoo import models


class CapabilityUpgradeService(models.AbstractModel):
    _name = "plasticos.capability.upgrade.service"
    _description = "Capability Upgrade Intelligence"

    def suggest(self):
        driver = self.env["plasticos.neo4j.driver"]

        query = """
        MATCH (f:Facility)-[:SUCCESS_WITH]->(g1:Grade)
        MATCH (g1)-[s:SIMILAR_TO]->(g2:Grade)
        WHERE s.score_structural > 0.85
          AND NOT (f)-[:SUCCESS_WITH]->(g2)
        RETURN
          f.facility_id AS facility_id,
          g2.grade_id AS grade_id,
          s.score_structural AS similarity
        ORDER BY similarity DESC
        LIMIT 500
        """

        return driver.execute(query)

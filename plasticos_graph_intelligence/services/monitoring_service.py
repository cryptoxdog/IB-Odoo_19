from odoo import models


class GraphMonitoringService(models.AbstractModel):
    _name = "plasticos.graph.monitoring.service"
    _description = "Graph Monitoring Service"

    def kpis(self):
        driver = self.env["plasticos.neo4j.driver"]

        query = """
        MATCH (f:Facility)
        OPTIONAL MATCH (f)-[:SUCCESS_WITH]->(g)
        OPTIONAL MATCH (g)-[:SIMILAR_TO]->(g2)
        RETURN
          count(DISTINCT f) AS facility_count,
          count(DISTINCT g) AS active_grades,
          count(DISTINCT g2) AS similarity_links
        """

        return driver.execute(query)[0]

from odoo import models


class GraphVisualizationService(models.AbstractModel):
    _name = "plasticos.graph.visualization.service"
    _description = "Graph Visualization Service"

    def intake_subgraph(self, intake_id):
        driver = self.env["plasticos.neo4j.driver"]
        query = """
        MATCH path =
          (i:Intake {intake_id:$intake_id})-[:HAS_PROFILE]->(mp)
          -[:QUALIFIES_FOR]->(g)
          <-[:CAN_RUN]-(cp)<-[:HAS_CAPABILITY]-(f)
        RETURN nodes(path) AS nodes, relationships(path) AS rels
        """
        return driver.execute(query, {"intake_id": intake_id})

    def grade_neighborhood(self, grade_id):
        driver = self.env["plasticos.neo4j.driver"]
        query = """
        MATCH (g:Grade {grade_id:$grade_id})-[r:SIMILAR_TO]-(n:Grade)
        RETURN g, r, n
        ORDER BY r.score_structural DESC
        LIMIT 50
        """
        return driver.execute(query, {"grade_id": grade_id})

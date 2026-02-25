from odoo import models


class MatchingEngine(models.AbstractModel):
    _name = "plasticos.graph.matching.engine"

    def generate_candidates(self, intake_id, mode="strict"):
        driver = self.env["plasticos.neo4j.driver"]

        if mode == "strict":
            query = open("/opt/graph_queries/strict_mode.cypher").read()
        else:
            query = open("/opt/graph_queries/relaxed_mode.cypher").read()

        return driver.execute(query, {"id": intake_id})

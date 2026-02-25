from odoo import models


class FederatedProjectionBuilder(models.AbstractModel):
    _name = "plasticos.graph.federation.projection"

    def build(self):
        driver = self.env["plasticos.neo4j.cluster.driver"]
        driver.execute_on_db(
            "graph_market_intel",
            """
        CALL gds.graph.project(
          'federated_projection',
          'Grade',
          'MARKET_SIMILAR'
        )
        """,
        )

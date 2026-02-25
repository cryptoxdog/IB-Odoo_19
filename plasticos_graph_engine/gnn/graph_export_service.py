from odoo import models


class GNNGraphExport(models.AbstractModel):
    _name = "plasticos.graph.gnn.export"

    def export(self, tenant_code):
        router = self.env["plasticos.graph.tenant.router"]
        db = router.get_database(tenant_code)
        driver = self.env["plasticos.neo4j.cluster.driver"]

        nodes = driver.execute_on_db(
            db,
            """
        MATCH (g:Grade)
        RETURN id(g) AS id, g.tier_level AS tier, g.mfi_min AS mfi_min, g.mfi_max AS mfi_max
        """,
        )

        edges = driver.execute_on_db(
            db,
            """
        MATCH (a:Grade)-[:SIMILAR_TO]->(b:Grade)
        RETURN id(a) AS source, id(b) AS target
        """,
        )

        return {"nodes": nodes, "edges": edges}

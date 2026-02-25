from odoo import models


class ClusterValidationService(models.AbstractModel):
    _name = "plasticos.graph.cluster.validation"
    _description = "Cluster Density Validator"

    def validate(self, cluster):
        driver = self.env["plasticos.neo4j.cluster.driver"]

        result = driver.execute_on_db(
            "graph_control",
            """
        MATCH (g:Grade)
        WHERE g.community_id = $cid
        WITH collect(g) AS nodes
        UNWIND nodes AS a
        UNWIND nodes AS b
        MATCH (a)-[r:SIMILAR_TO]-(b)
        RETURN count(r) AS edges
        """,
            {"cid": cluster["cluster_id"]},
        )

        size = cluster["size"]
        max_edges = size * (size - 1) / 2
        density = result[0]["edges"] / max_edges if max_edges else 0

        return density

from odoo import models


class CommunityDetectionService(models.AbstractModel):
    _name = "plasticos.graph.community.detection"
    _description = "GDS Community Detection"

    def detect(self):
        driver = self.env["plasticos.neo4j.cluster.driver"]

        driver.execute_on_db(
            "graph_control",
            """
        CALL gds.graph.project(
          'reinforcement_projection',
          'Grade',
          {
            SIMILAR_TO: {orientation:'UNDIRECTED'}
          }
        )
        """,
        )

        driver.execute_on_db(
            "graph_control",
            """
        CALL gds.louvain.write('reinforcement_projection', {
          writeProperty: 'community_id'
        })
        """,
        )

        result = driver.execute_on_db(
            "graph_control",
            """
        MATCH (g:Grade)
        WITH g.community_id AS cid, collect(g.grade_id) AS grades, count(*) AS size
        WHERE size > 3
        RETURN cid AS cluster_id, grades, size
        """,
        )

        return result

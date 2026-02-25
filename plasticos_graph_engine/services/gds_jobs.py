from odoo import models


class GraphGDSJobs(models.AbstractModel):
    _name = "plasticos.graph.gds"

    def compute_grade_similarity(self):
        driver = self.env["plasticos.neo4j.driver"]

        driver.execute("""
        CALL gds.graph.project(
          'grade_structural',
          'Grade',
          {
            USES_POLYMER: {orientation:'UNDIRECTED'},
            COMPATIBLE_WITH_PROCESS: {orientation:'UNDIRECTED'},
            REQUIRES_TIER: {orientation:'UNDIRECTED'}
          }
        )
        """)

        driver.execute("""
        CALL gds.nodeSimilarity.write('grade_structural', {
          writeRelationshipType: 'SIMILAR_TO',
          writeProperty: 'score_structural'
        })
        """)

        driver.execute("""
        CALL gds.fastRP.write('grade_structural', {
          embeddingDimension: 64,
          writeProperty: 'embedding'
        })
        """)

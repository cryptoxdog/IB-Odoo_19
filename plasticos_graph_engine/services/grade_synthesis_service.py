import uuid

from odoo import models


class GradeSynthesisService(models.AbstractModel):
    _name = "plasticos.graph.grade.synthesis"
    _description = "Emergent Grade Synthesizer"

    def synthesize(self, cluster_id, grades):
        driver = self.env["plasticos.neo4j.cluster.driver"]

        centroid = driver.execute_on_db(
            "graph_control",
            """
        MATCH (g:Grade)
        WHERE g.grade_id IN $grades
        RETURN avg(g.tier_level) AS tier_avg,
               avg(g.mfi_min) AS mfi_min_avg,
               avg(g.mfi_max) AS mfi_max_avg
        """,
            {"grades": grades},
        )[0]

        proposed_code = f"EMERGENT_{uuid.uuid4().hex[:8]}"

        spec = {
            "tier_level": round(centroid["tier_avg"]),
            "mfi_min": centroid["mfi_min_avg"],
            "mfi_max": centroid["mfi_max_avg"],
            "origin_cluster": cluster_id,
        }

        cluster_rec = self.env["plasticos.graph.emergent.cluster"].search([("cluster_id", "=", cluster_id)], limit=1)

        return self.env["plasticos.graph.emergent.grade"].create(
            {
                "cluster_id": cluster_rec.id,
                "proposed_grade_code": proposed_code,
                "proposed_spec": spec,
            }
        )

from odoo import models


class EmergentGradeRegistry(models.AbstractModel):
    _name = "plasticos.graph.emergent.registry"

    def materialize(self, emergent_grade_id):
        record = self.env["plasticos.graph.emergent.grade"].browse(emergent_grade_id)
        if record.approval_status != "approved":
            return

        driver = self.env["plasticos.neo4j.cluster.driver"]

        driver.execute_on_db(
            "graph_control",
            """
        MERGE (g:Grade {grade_id:$gid})
        SET g.tier_level=$tier,
            g.mfi_min=$mfi_min,
            g.mfi_max=$mfi_max,
            g.emergent=true
        """,
            {
                "gid": record.proposed_grade_code,
                "tier": record.proposed_spec["tier_level"],
                "mfi_min": record.proposed_spec["mfi_min"],
                "mfi_max": record.proposed_spec["mfi_max"],
            },
        )

        record.cluster_id.write({"status": "materialized"})

from odoo import models


class GraphAnomalyGDS(models.AbstractModel):
    _name = "plasticos.graph.anomaly.gds"
    _description = "Anomaly GDS Projection"

    def detect_outliers(self, tenant_code):
        router = self.env["plasticos.graph.tenant.router"]
        db = router.get_database(tenant_code)
        driver = self.env["plasticos.neo4j.cluster.driver"]

        driver.execute_on_db(
            db,
            """
        CALL gds.degree.write('facility_projection', {
            writeProperty: 'degree_score'
        })
        """,
        )

        return driver.execute_on_db(
            db,
            """
        MATCH (f:Facility)
        WHERE f.degree_score < 2
        RETURN f.facility_id AS facility_id
        """,
        )

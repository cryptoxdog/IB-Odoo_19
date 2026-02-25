from odoo import models


class GraphAnomalyDetector(models.AbstractModel):
    _name = "plasticos.graph.anomaly.detector"
    _description = "Graph Anomaly Detector"

    def detect_transaction_spike(self, tenant_code):
        router = self.env["plasticos.graph.tenant.router"]
        db = router.get_database(tenant_code)
        driver = self.env["plasticos.neo4j.cluster.driver"]

        result = driver.execute_on_db(
            db,
            """
        MATCH (f:Facility)-[:SUCCESS_WITH]->(g:Grade)
        WITH f, count(g) AS success_count
        WHERE success_count > 50
        RETURN f.facility_id AS facility_id, success_count
        """,
        )

        tenant = self.env["plasticos.graph.tenant"].search([("tenant_code", "=", tenant_code)], limit=1)

        for row in result:
            self.env["plasticos.graph.anomaly"].create(
                {
                    "tenant_id": tenant.id,
                    "anomaly_type": "transaction_spike",
                    "entity_id": row["facility_id"],
                    "severity": row["success_count"],
                    "metadata": row,
                }
            )

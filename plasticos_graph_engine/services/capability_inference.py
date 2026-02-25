from odoo import models


class CapabilityInference(models.AbstractModel):
    _name = "plasticos.graph.capability.inference"

    def build_capabilities(self):
        driver = self.env["plasticos.neo4j.driver"]

        driver.execute("""
        MATCH (f:Facility)
        OPTIONAL MATCH (f)<-[:BETWEEN]-(t:Transaction)-[:INVOLVES]->(g:Grade)
        WITH f, collect(distinct g) AS grades
        MERGE (c:CapabilityProfile {capability_id: f.facility_id})
        MERGE (f)-[:HAS_CAPABILITY]->(c)
        FOREACH (g IN grades |
            MERGE (c)-[:CAN_RUN]->(g)
        )
        """)

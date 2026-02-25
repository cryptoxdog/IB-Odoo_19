from odoo import models


class ReinforcementBuilder(models.AbstractModel):
    _name = "plasticos.graph.reinforcement"

    def rebuild(self):
        driver = self.env["plasticos.neo4j.driver"]

        driver.execute("""
        MATCH (t:Transaction)-[:BETWEEN]->(f)
        MATCH (t)-[:INVOLVES]->(g)
        WITH f,g,count(*) AS txn_count
        MERGE (f)-[r:SUCCESS_WITH]->(g)
        SET r.txn_count = txn_count
        """)

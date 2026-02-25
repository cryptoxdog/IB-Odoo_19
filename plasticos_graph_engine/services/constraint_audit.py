"""Graph constraint audit service.

Checks for data integrity violations in the Neo4j graph, such as
MaterialProfile nodes missing required HAS_POLYMER relationships.
"""

from odoo import models


class ConstraintAudit(models.AbstractModel):
    _name = "plasticos.graph.constraint.audit"
    _description = "Graph Constraint Audit"

    def run(self):
        """Return count of MaterialProfile nodes missing HAS_POLYMER."""
        driver = self.env["plasticos.neo4j.driver"]
        result = driver.execute("""
        MATCH (mp:MaterialProfile)
        WHERE NOT (mp)-[:HAS_POLYMER]->()
        RETURN count(mp) AS missing_polymer
        """)
        return result[0]["missing_polymer"] if result else 0

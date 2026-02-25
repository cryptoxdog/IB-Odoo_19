"""Reinforcement edge builder.

Rebuilds SUCCESS_WITH relationships between Facility and Grade nodes
based on transaction history, including recency-weighted scoring.

Consolidates the logic from the standalone ``reinforcement_rebuilder.py``
into the Odoo-integrated service.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ReinforcementBuilder(models.AbstractModel):
    _name = "plasticos.graph.reinforcement"
    _description = "Graph Reinforcement Edge Builder"

    def rebuild(self):
        """Delete stale SUCCESS_WITH edges and rebuild with recency weighting."""
        driver = self.env["plasticos.neo4j.driver"]

        # Phase 1: Clear stale edges
        driver.execute("""
        MATCH (f:Facility)-[r:SUCCESS_WITH]->()
        DELETE r
        """)

        # Phase 2: Rebuild with transaction count + recency decay
        driver.execute("""
        MATCH (t:Transaction)-[:BETWEEN]->(f)
        MATCH (t)-[:INVOLVES]->(g)
        WITH f, g,
             count(*) AS txn_count,
             max(t.date) AS last_txn
        MERGE (f)-[r:SUCCESS_WITH]->(g)
        SET r.score = txn_count,
            r.txn_count = txn_count,
            r.recency_weight = CASE
                WHEN last_txn IS NOT NULL
                THEN exp(-duration.inDays(last_txn, date()).days / 90.0)
                ELSE 0.5
            END
        """)

        _logger.info("Reinforcement edges rebuilt")

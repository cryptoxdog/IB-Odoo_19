"""Neo4j schema bootstrap manager.

Creates uniqueness constraints and indexes required by the graph
ontology.  All statements are idempotent (IF NOT EXISTS).
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class GraphSchemaManager(models.AbstractModel):
    _name = "plasticos.graph.schema.manager"
    _description = "Graph Schema Bootstrap Manager"

    def bootstrap(self):
        driver = self.env["plasticos.neo4j.driver"]

        constraints = [
            "CREATE CONSTRAINT grade_id IF NOT EXISTS FOR (g:Grade) REQUIRE g.grade_id IS UNIQUE",
            "CREATE CONSTRAINT facility_id IF NOT EXISTS FOR (f:Facility) REQUIRE f.facility_id IS UNIQUE",
            "CREATE CONSTRAINT profile_id IF NOT EXISTS FOR (m:MaterialProfile) REQUIRE m.profile_id IS UNIQUE",
            "CREATE CONSTRAINT txn_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.txn_id IS UNIQUE",
            "CREATE CONSTRAINT polymer_code IF NOT EXISTS FOR (p:Polymer) REQUIRE p.code IS UNIQUE",
            "CREATE CONSTRAINT tier_level IF NOT EXISTS FOR (t:Tier) REQUIRE t.level IS UNIQUE",
        ]

        for q in constraints:
            driver.execute(q)

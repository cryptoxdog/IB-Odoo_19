"""Shard-aware matching engine extension.

Routes graph queries to the correct Neo4j database shard based on
facility hash.  Falls back to the control database when no facility
is specified.
"""

from odoo import models


class MatchingEngineShard(models.AbstractModel):
    _inherit = "plasticos.graph.matching.engine"

    def generate_candidates(self, intake_id, mode="strict", facility_id=None):
        shard_router = self.env["plasticos.shard.router"]
        cluster_driver = self.env["plasticos.neo4j.cluster.driver"]

        if facility_id:
            db = shard_router.get_shard_db(facility_id)
        else:
            db = shard_router.CONTROL_DB

        if mode == "strict":
            query = self._strict_query()
        else:
            query = self._relaxed_query()

        return cluster_driver.execute_on_db(db, query, {"id": intake_id})

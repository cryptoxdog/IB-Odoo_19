"""Graph-based matching engine for intake → facility candidate generation."""

import os

from odoo import models

_QUERY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "queries")


def _load_query(filename: str) -> str:
    """Load a Cypher query file from the module's queries directory."""
    path = os.path.join(_QUERY_DIR, filename)
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class MatchingEngine(models.AbstractModel):
    _name = "plasticos.graph.matching.engine"
    _description = "Graph Matching Engine"

    def _strict_query(self):
        return _load_query("strict_mode.cypher")

    def _relaxed_query(self):
        return _load_query("relaxed_mode.cypher")

    def generate_candidates(self, intake_id, mode="strict"):
        """Generate facility candidates for an intake via graph traversal."""
        driver = self.env["plasticos.neo4j.driver"]
        query = self._strict_query() if mode == "strict" else self._relaxed_query()
        return driver.execute(query, {"id": intake_id})

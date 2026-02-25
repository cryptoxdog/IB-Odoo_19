"""Explainability builder for graph match results."""

from odoo import models


class ExplainabilityBuilder(models.AbstractModel):
    _name = "plasticos.graph.explainability.builder"
    _description = "Graph Match Explainability Builder"

    def build_explanation(self, record):
        """Build a human-readable explanation dict from a scoring record."""
        return {
            "intake": record.get("intake"),
            "facility": record.get("facility"),
            "score": record.get("S_total"),
            "components": {
                "structural": 1.0,
                "quality": record.get("S_contam"),
                "geo": record.get("S_geo"),
                "reinforcement": record.get("S_reinf"),
            },
        }

"""Intake hooks for graph-based buyer matching.

Moved from Buyer Matching Using Neo4j/intake_hooks.py;
realigned to trigger graph match only (no vector/embedding).
When an intake is normalized, optionally run graph buyer match
and append results to plasticos.match.result.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IntakeGraphHooks(models.Model):
    """Extend plasticos.intake to run graph buyer match when normalized."""

    _inherit = "plasticos.intake"

    def write(self, vals):
        result = super().write(vals)
        if "normalized" in vals and vals.get("normalized"):
            for intake in self:
                if intake.material_profile_id:
                    self._run_graph_match_if_available(intake)
        return result

    def _run_graph_match_if_available(self, intake):
        """Run graph-based buyer match and append results if graph service is configured."""
        if not self.env.get("plasticos.graph.service"):
            return
        try:
            self.env["plasticos.graph.service"].sudo().match_buyers_for_intake(intake)
        except Exception as exc:
            _logger.warning("Graph match for intake %s skipped: %s", intake.id, exc)

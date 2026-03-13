"""Intake hooks for buyer matching v2.0.

When an intake is normalized, automatically run buyer matching
using the v2.0 plasticos.buyer.matcher model which handles:
  - Stage 1: Python hard-gating via facility.profile
  - Stage 2: Neo4j scoring via graph_service.calculate_match_score()

Results are written to plasticos.match.result.
"""

import logging

from odoo import models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class IntakeGraphHooks(models.Model):
    """Extend plasticos.intake to run buyer match when normalized."""

    _inherit = "plasticos.intake"

    def write(self, vals):
        result = super().write(vals)
        if "normalized" in vals and vals.get("normalized"):
            for intake in self:
                if intake.material_profile_id:
                    self._run_buyer_match_if_available(intake)
        return result

    def _run_buyer_match_if_available(self, intake):
        """Run v2.0 buyer matching when intake is normalized.

        Uses plasticos.buyer.matcher which internally calls
        graph_service.calculate_match_score() for Neo4j scoring.
        """
        gate = self.env["plasticos.feature.gate.mixin"]
        if gate._skip_feature_gate_for_cron("plasticos.matching_engine.enabled", "intake_normalized_auto_match"):
            return

        try:
            matcher = self.env["plasticos.buyer.matcher"]
            matches = matcher.find_matches_for_supplier(
                supplier_partner_id=intake.partner_id.id, intake_id=intake.id, max_results=20
            )
            _logger.info("Auto-match for normalized intake %s: found %d matches", intake.id, len(matches))
        except (UserError, ValidationError):
            raise
        except Exception as exc:
            _logger.warning("Buyer match for intake %s skipped: %s", intake.id, exc)

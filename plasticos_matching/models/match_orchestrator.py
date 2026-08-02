"""Gate-only match orchestrator (mothball M2). No local scoring/discovery."""

from __future__ import annotations

import logging
import uuid

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PlasticosMatchOrchestrator(models.AbstractModel):
    """Orchestrates buyer matching exclusively through Constellation Gate.

    Hard rules (ADR-003-single / M2):
    - No Neo4j / local Stage-1 candidate discovery in this addon
    - No silent fallback to plasticos.buyer.matcher local path
    - Failures are classified and recorded on plasticos.match.run
    """

    _name = "plasticos.match.orchestrator"
    _description = "Gate-Only Match Orchestrator"

    @api.model
    def run_match_for_intake(self, intake, max_results=20, mode="strict"):
        """Execute Gate match for one intake; return (run, matches).

        Raises UserError on classified permanent/unknown failures after recording
        the run. Does not invoke local matcher scoring.
        """
        intake.ensure_one()
        if not intake.partner_id:
            raise UserError(_("Intake has no supplier partner."))
        if not intake.material_profile_id:
            raise UserError(
                _("Intake '%s' has no material profile. Link a material profile before matching.")
                % (intake.display_name,)
            )

        MatchRun = self.env["plasticos.match.run"]
        run = MatchRun.create(
            {
                "intake_id": intake.id,
                "supplier_partner_id": intake.partner_id.id,
                "mode": mode or "strict",
                "state": "pending",
                "engine": "gate",
            }
        )

        from odoo.addons.plasticos_gate.services.gate_config import (
            GateIntegrationError,
            gate_matching_enabled,
        )
        from odoo.addons.plasticos_gate.services.gate_builders import build_match_request
        from odoo.addons.plasticos_gate.services.gate_client import (
            classify_transport_failure,
            send_match_action,
        )
        from odoo.addons.plasticos_gate.services.gate_mappers import (
            extract_audit_metadata,
            map_match_response,
            map_match_response_to_matcher_dicts,
        )

        if not gate_matching_enabled(self.env):
            run.write(
                {
                    "state": "failed",
                    "failure_class": "permanent",
                    "error_message": "Gate matching not enabled (URL/SDK/ICP).",
                }
            )
            raise UserError(
                _("Gate matching is not enabled. Configure plasticos.gate.url and matching ICP.")
            )

        try:
            request = build_match_request(
                self.env, intake=intake, top_n=max_results, mode=mode or "strict"
            )
            correlation_id = request.odoo.get("correlation_id") if request.odoo else None
            gate_result = send_match_action(
                self.env,
                payload=request.to_dict(),
                correlation_id=correlation_id,
            )
            mapped = map_match_response(gate_result["payload"])
            audit = extract_audit_metadata(gate_result["packet"])
            matches = map_match_response_to_matcher_dicts(mapped, audit_metadata=audit)
        except GateIntegrationError as exc:
            failure = getattr(exc, "failure_class", None) or classify_transport_failure(exc).value
            run.write(
                {
                    "state": "failed",
                    "failure_class": failure,
                    "error_message": str(exc),
                }
            )
            _logger.warning("Gate-only match failed for intake %s: %s", intake.id, exc)
            raise UserError(
                _("Gate match failed (%s): %s") % (failure, exc)
            ) from exc
        except (UserError, ValidationError):
            raise
        except Exception as exc:  # noqa: BLE001 — boundary: classify then fail closed
            failure = classify_transport_failure(exc).value
            run.write(
                {
                    "state": "failed",
                    "failure_class": failure,
                    "error_message": str(exc),
                }
            )
            _logger.exception("Gate-only match unexpected error for intake %s", intake.id)
            raise UserError(_("Gate match failed (%s): %s") % (failure, exc)) from exc

        # Apply exclusion policy (identity: plasticos.match.exclusion)
        excluded = set(self.env["plasticos.match.exclusion"].get_excluded_buyer_ids(intake.partner_id.id))
        if excluded:
            matches = [m for m in matches if m.get("buyer_id") not in excluded]

        matches = matches[:max_results]
        packet_id = None
        corr = None
        if matches:
            packet_id = matches[0].get("gate_packet_id")
            corr = matches[0].get("gate_correlation_id")

        run.write(
            {
                "state": "ok",
                "match_count": len(matches),
                "gate_packet_id": packet_id,
                "gate_correlation_id": corr,
                "failure_class": False,
                "error_message": False,
            }
        )
        return run, matches

    @api.model
    def persist_review_results(self, intake, matches, run):
        """Persist UI lines + canonical match.result rows linked to the run."""
        run_id = str(uuid.uuid4())
        intake.match_line_ids.unlink()
        for m in matches:
            buyer_id = m.get("buyer_id")
            if not buyer_id:
                continue
            self.env["plasticos.intake.match"].create(
                {
                    "intake_id": intake.id,
                    "buyer_id": buyer_id,
                    "match_score": (m.get("total_score") or 0.0) * 100,
                    "match_reason": ", ".join(m.get("gates_failed") or []) or "All gates passed",
                    "typical_price": m.get("typical_price") or 0.0,
                }
            )
        if "plasticos.match.result.writer" in self.env:
            created = self.env["plasticos.match.result.writer"].persist_match_lines(
                intake, matches, run_id=run_id
            )
            if created and run:
                created.write({"match_run_id": run.id})
        return run_id

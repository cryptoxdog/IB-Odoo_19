"""Gate-only match orchestrator (mothball M2/M3). No local scoring/discovery."""

from __future__ import annotations

import hashlib
import json
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

_RETRYABLE = "retryable"
_PERMANENT = "permanent"
_UNKNOWN = "unknown"


def _canonical_digest(value):
    """Return a deterministic SHA-256 digest of Gate request or response material."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _receipt_text(value):
    """Allow only scalar text to cross from an untrusted Gate payload into an Odoo Char field."""
    return value if isinstance(value, str) and value.strip() else False


class PlasticosMatchOrchestrator(models.AbstractModel):
    """Orchestrates buyer matching exclusively through Constellation Gate.

    Hard rules (ADR-003-single / M2 / M3):
    - No Neo4j / local Stage-1 candidate discovery in this addon
    - No silent fallback to plasticos.buyer.matcher local path
    - Gate failures are classified, audited on plasticos.match.run, and fail closed
    - Retryable failures expose operator retry; never substitute empty success
    """

    _name = "plasticos.match.orchestrator"
    _description = "Gate-Only Match Orchestrator"

    @api.model
    def _state_for_failure(self, failure_class: str) -> str:
        if failure_class == _RETRYABLE:
            return "retryable"
        if failure_class == _PERMANENT:
            return "failed"
        return "degraded"

    @api.model
    def run_match_for_intake(self, intake, max_results=20, mode="strict", *, retry_of=None):
        """Execute Gate match for one intake; return (run, matches).

        Raises UserError on classified failures after recording the run.
        Does not invoke local matcher scoring under any failure class.
        """
        intake.ensure_one()
        if not intake.partner_id:
            raise UserError(_("Intake has no supplier partner."))
        if not intake.material_profile_id:
            raise UserError(
                _("Intake '%s' has no material profile. Link a material profile before matching.")
                % (intake.display_name,)
            )

        from odoo.addons.plasticos_gate.services.gate_builders import (
            build_match_request,
            build_operation_id,
        )
        from odoo.addons.plasticos_gate.services.gate_client import (
            classify_transport_failure,
            send_match_action,
        )
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateCapability,
            GateIntegrationError,
            classify_gate_availability,
            gate_matching_enabled,
        )
        from odoo.addons.plasticos_gate.services.gate_mappers import (
            extract_audit_metadata,
            map_match_response,
            map_match_response_to_matcher_dicts,
        )

        availability = classify_gate_availability(self.env, capability=GateCapability.MATCHING)
        MatchRun = self.env["plasticos.match.run"]
        vals = {
            "intake_id": intake.id,
            "supplier_partner_id": intake.partner_id.id,
            "mode": mode or "strict",
            "state": "pending",
            "engine": "gate",
            "availability_status": availability.status,
            "request_attempt": (retry_of.request_attempt + 1) if retry_of else 1,
        }
        if retry_of:
            vals["retry_of_id"] = retry_of.id
        run = MatchRun.create(vals)

        if not gate_matching_enabled(self.env):
            reasons = "; ".join(availability.reasons) or "Gate matching unavailable"
            run.write(
                {
                    "state": "failed",
                    "failure_class": _PERMANENT,
                    "error_message": reasons,
                    "availability_status": availability.status,
                }
            )
            raise UserError(
                _("Gate matching is not enabled (%(status)s): %(reasons)s")
                % {"status": availability.status, "reasons": reasons}
            )

        try:
            request = build_match_request(
                self.env,
                intake=intake,
                match_run=run,
                top_n=max_results,
                mode=mode or "strict",
            )
            correlation_id = request.odoo.get("correlation_id") if request.odoo else None
            operation_id = build_operation_id(
                request.odoo,
                family="matching",
                attempt=run.request_attempt,
            )
            if not operation_id:
                raise ValidationError(_("Gate match request has no durable Odoo operation identity."))
            request_payload = request.to_dict()
            # Persist the exact Odoo request identity and material fingerprint before Gate dispatch.
            run.write(
                {
                    "operation_id": operation_id,
                    "request_fingerprint": _canonical_digest(request_payload),
                }
            )
            gate_result = send_match_action(
                self.env,
                payload=request_payload,
                correlation_id=correlation_id,
                idempotency_key=operation_id,
            )
            audit = extract_audit_metadata(gate_result["packet"])
            response_payload = gate_result["payload"]
            # Preserve Gate provenance before payload mapping. A zero-candidate response is still a receipt.
            run.write(
                {
                    "gate_packet_id": audit["gate_packet_id"],
                    "gate_correlation_id": audit["gate_correlation_id"],
                    "gate_response_digest": _canonical_digest(response_payload),
                }
            )
            mapped = map_match_response(response_payload)
            matches = map_match_response_to_matcher_dicts(mapped, audit_metadata=audit)
        except GateIntegrationError as exc:
            failure = getattr(exc, "failure_class", None) or classify_transport_failure(exc).value
            run.write(
                {
                    "state": self._state_for_failure(failure),
                    "failure_class": failure,
                    "error_message": str(exc),
                }
            )
            _logger.warning("Gate-only match failed for intake %s: %s", intake.id, exc)
            raise UserError(_("Gate match failed (%s): %s") % (failure, exc)) from exc
        except (UserError, ValidationError) as exc:
            run.write(
                {
                    "state": "failed",
                    "failure_class": _PERMANENT,
                    "error_message": str(exc),
                }
            )
            raise
        except Exception as exc:  # noqa: BLE001 — boundary: classify then fail closed
            failure = classify_transport_failure(exc).value
            run.write(
                {
                    "state": self._state_for_failure(failure),
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
        run.write(
            {
                "state": "ok",
                "match_count": len(matches),
                "gate_query_id": _receipt_text(mapped.query_id),
                "gate_contract_version": _receipt_text(mapped.contract_version),
                "gate_domain_spec_version": _receipt_text(mapped.domain_spec_version),
                "gate_model_version": _receipt_text(mapped.model_version),
                "failure_class": False,
                "error_message": False,
            }
        )
        return run, matches

    @api.model
    def retry_match_run(self, prior_run):
        """Retry a prior non-ok run. Suppresses duplicate retries while pending."""
        prior_run.ensure_one()
        if prior_run.state == "ok":
            raise UserError(_("Match run %s already succeeded.") % prior_run.id)
        pending = self.env["plasticos.match.run"].search(
            [
                ("intake_id", "=", prior_run.intake_id.id),
                ("state", "=", "pending"),
                ("retry_of_id", "=", prior_run.id),
            ],
            limit=1,
        )
        if pending:
            raise UserError(_("A retry is already pending for run %s (pending run %s).") % (prior_run.id, pending.id))
        run, matches = self.run_match_for_intake(
            prior_run.intake_id,
            max_results=20,
            mode=prior_run.mode or "strict",
            retry_of=prior_run,
        )
        self.persist_review_results(prior_run.intake_id, matches, run)
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Run"),
            "res_model": "plasticos.match.run",
            "res_id": run.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _build_intake_match_line_vals(self, intake, matches):
        """Build vals for plasticos.intake.match rows (no ORM writes)."""
        vals = []
        for m in matches:
            buyer_id = m.get("buyer_id")
            if not buyer_id:
                continue
            vals.append(
                {
                    "intake_id": intake.id,
                    "buyer_id": buyer_id,
                    "match_score": (m.get("total_score") or 0.0) * 100,
                    "match_reason": ", ".join(m.get("gates_failed") or []) or "All gates passed",
                    "typical_price": m.get("typical_price") or 0.0,
                }
            )
        return vals

    @api.model
    def _create_intake_match_lines(self, vals_list):
        """Batch-create UI match lines (kept loop-free for audit scanner)."""
        if not vals_list:
            return self.env["plasticos.intake.match"]
        return self.env["plasticos.intake.match"].create(vals_list)

    @api.model
    def persist_review_results(self, intake, matches, run):
        """Persist UI lines + canonical match.result rows linked to the run."""
        run.ensure_one()
        # Canonical review rows are durable receipt projections. Persist them before
        # transient intake display lines so a UI-only update cannot masquerade as a result.
        try:
            self.env["plasticos.match.result.writer"].persist_match_lines(
                intake,
                matches,
                match_run=run,
            )
        except (AccessError, ValidationError) as exc:
            run.write(
                {
                    "state": "failed",
                    "failure_class": _PERMANENT,
                    "error_message": str(exc),
                }
            )
            raise
        intake.match_line_ids.unlink()
        self._create_intake_match_lines(self._build_intake_match_line_vals(intake, matches))
        return run.operation_id

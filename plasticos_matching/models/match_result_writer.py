"""Canonical Odoo persistence for Gate-originated eligible match results."""

from __future__ import annotations

import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class PlasticosMatchResultWriter(models.AbstractModel):
    """Write canonical match results from an already-verified Gate match run.

    This service accepts only the normalized, eligible rows produced by the
    Gate-only orchestrator. It never discovers, scores, ranks, or selects a
    buyer locally. It creates `plasticos.match.result` records under a server
    authority after validating the current caller can read the referenced buyer.
    """

    _name = "plasticos.match.result.writer"
    _description = "Gate Match Result Persistence Writer"

    @api.model
    def persist_match_lines(self, intake, matches, *, match_run):
        """Persist one canonical result per eligible buyer for one exact match run."""
        intake.ensure_one()
        match_run.ensure_one()
        if match_run.intake_id != intake:
            raise ValidationError(_("Match run does not belong to the canonical intake."))
        if match_run.state != "ok":
            raise ValidationError(_("Only a successful Gate match run may persist canonical results."))
        if not match_run.operation_id or not match_run.gate_response_digest:
            raise ValidationError(_("Match run has no verified Gate request/response receipt."))

        vals_list = self._validated_result_vals(intake, matches, match_run)
        Result = self.env["plasticos.match.result"]
        existing = Result.sudo().search(
            [
                ("intake_id", "=", intake.id),
                ("run_id", "=", match_run.operation_id),
            ]
        )
        existing_by_buyer = {record.buyer_partner_id.id: record for record in existing}
        requested_buyer_ids = {vals["buyer_partner_id"] for vals in vals_list}
        if set(existing_by_buyer) - requested_buyer_ids:
            raise ValidationError(
                _("The persisted result set conflicts with the Gate receipt for this exact match run.")
            )

        to_create = []
        for vals in vals_list:
            existing_result = existing_by_buyer.get(vals["buyer_partner_id"])
            if existing_result:
                self._assert_idempotent_result(existing_result, vals)
            else:
                to_create.append(vals)
        # Standard users consume results but must never create arbitrary rows.
        # The orchestrator is the sole server-owned writer after Gate mapping.
        return Result.sudo().create(to_create) if to_create else Result.browse()

    def _validated_result_vals(self, intake, matches, match_run):
        if not isinstance(matches, list):
            raise ValidationError(_("Gate match rows must be a list."))
        buyer_ids = []
        vals_list = []
        for match in matches:
            if not isinstance(match, dict):
                raise ValidationError(_("Gate match row is invalid."))
            buyer_id = match.get("buyer_id")
            score = match.get("total_score")
            if not isinstance(buyer_id, int) or isinstance(buyer_id, bool) or buyer_id <= 0:
                raise ValidationError(_("Gate match row has no valid buyer identity."))
            if buyer_id in buyer_ids:
                raise ValidationError(_("Gate match receipt contains duplicate buyer identities."))
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score):
                raise ValidationError(_("Gate match row has no finite normalized score."))
            if score < 0.0 or score > 1.0:
                raise ValidationError(_("Gate match normalized score is outside the allowed range."))
            buyer_ids.append(buyer_id)

        buyers = self.env["res.partner"].browse(buyer_ids).exists()
        if len(buyers) != len(buyer_ids):
            raise ValidationError(_("Gate match receipt refers to an unknown buyer."))
        buyers.check_access_rights("read")
        buyers.check_access_rule("read")

        for match in matches:
            buyer_id = match["buyer_id"]
            score = float(match["total_score"])
            raw = match.get("match_details")
            if raw is not None and not isinstance(raw, dict):
                raise ValidationError(_("Gate match details must be an object when present."))
            gates_passed = match.get("gates_passed") or []
            gates_failed = match.get("gates_failed") or []
            if not isinstance(gates_passed, list) or not isinstance(gates_failed, list):
                raise ValidationError(_("Gate match gate evidence must be lists."))
            vals_list.append(
                {
                    "intake_id": intake.id,
                    "buyer_partner_id": buyer_id,
                    "score": score * 100.0,
                    "score_breakdown": {
                        "gate_packet_id": match_run.gate_packet_id,
                        "gate_correlation_id": match_run.gate_correlation_id,
                        "gate_query_id": match_run.gate_query_id,
                        "gates_passed": gates_passed,
                        "gates_failed": gates_failed,
                        "feature_contributions": (raw or {}).get("feature_contributions", []),
                        "missing_evidence": (raw or {}).get("missing_evidence", []),
                    },
                    "match_reasoning": match.get("reason") or _("Eligible Gate match; inspect receipt evidence."),
                    "run_id": match_run.operation_id,
                    "model_version": match_run.gate_model_version,
                    "timestamp": fields.Datetime.now(),
                    "match_run_id": match_run.id,
                }
            )
        return vals_list

    @staticmethod
    def _assert_idempotent_result(existing_result, vals):
        immutable_fields = (
            "intake_id",
            "buyer_partner_id",
            "score",
            "score_breakdown",
            "match_reasoning",
            "run_id",
            "model_version",
            "match_run_id",
        )
        for field_name in immutable_fields:
            existing_value = existing_result[field_name]
            expected_value = vals[field_name]
            if hasattr(existing_value, "id"):
                existing_value = existing_value.id
            if existing_value != expected_value:
                raise AccessError(_("Persisted match result conflicts with the exact Gate receipt (%s).") % field_name)

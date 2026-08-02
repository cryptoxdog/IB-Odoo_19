import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MATCH_ENGINE_VERSION = "2.0.0"


class MatchResultWriter(models.AbstractModel):
    """Mixin that persists intake.match lines into plasticos.match.result.

    Called by intake_extension.py after matching completes.
    Idempotent per run_id: never creates duplicate rows.
    Tenant-safe: all writes use the caller's environment (no sudo escalation
    beyond what is already present in the caller's context).
    """

    _name = "plasticos.match.result.writer"
    _description = "Match Result Persistence Helper"

    @api.model
    def persist_match_lines(self, intake, match_dicts, run_id=None):
        """Write a list of match dicts from the matcher into plasticos.match.result.

        Args:
            intake: plasticos.intake record
            match_dicts: list[dict] as returned by BuyerMatcher.find_matches_for_supplier
            run_id: optional run identifier (auto-generated UUID4 if omitted)

        Returns:
            plasticos.match.result recordset of newly created records
        """
        if not match_dicts:
            return self.env["plasticos.match.result"]

        run_id = run_id or str(uuid.uuid4())
        now = fields.Datetime.now()
        MatchResult = self.env["plasticos.match.result"]

        # Purge stale pending results for this intake before writing new ones.
        # Accepted/rejected results are immutable (guarded by model.write()).
        stale = MatchResult.search(
            [
                ("intake_id", "=", intake.id),
                ("state", "=", "pending"),
            ]
        )
        if stale:
            stale.unlink()

        created = MatchResult
        for m in match_dicts:
            buyer_id = m.get("buyer_id")
            if not buyer_id:
                _logger.warning("persist_match_lines: skipping result with no buyer_id")
                continue

            score_raw = m.get("total_score") or 0.0
            score_pct = round(min(max(score_raw * 100, 0.0), 100.0), 2)

            gates_failed = m.get("gates_failed") or []
            reasoning = "All gates passed" if not gates_failed else f"Gates failed: {', '.join(gates_failed)}"

            score_breakdown = {
                "total_score": score_raw,
                "gates_passed": m.get("gates_passed", 0),
                "gates_failed": gates_failed,
                "typical_price": m.get("typical_price", 0.0),
                "match_source": m.get("match_source", "local"),
                "gate_packet_id": m.get("gate_packet_id"),
                "gate_correlation_id": m.get("gate_correlation_id"),
            }
            if m.get("match_details"):
                score_breakdown["match_details"] = m["match_details"]

            vals = {
                "intake_id": intake.id,
                "buyer_partner_id": buyer_id,
                "facility_profile_id": m.get("facility_profile_id") or False,
                "score": score_pct,
                "confidence": score_pct,
                "score_breakdown": score_breakdown,
                "match_reasoning": reasoning,
                "run_id": run_id,
                "model_version": MATCH_ENGINE_VERSION,
                "timestamp": now,
                "state": "pending",
            }

            try:
                rec = MatchResult.create(vals)
                created |= rec
            except Exception as exc:
                _logger.error(
                    "Failed to persist match result for intake=%s buyer=%s: %s",
                    intake.id,
                    buyer_id,
                    exc,
                )

        _logger.info(
            "persist_match_lines: intake=%s run=%s created=%d records",
            intake.id,
            run_id,
            len(created),
        )
        return created

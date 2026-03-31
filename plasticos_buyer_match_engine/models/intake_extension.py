# PATCH FILE — replace plasticos_buyer_match_engine/models/intake_extension.py
# Changes:
#   1. After persisting intake.match lines, also call MatchResultWriter.persist_match_lines
#   2. Pass run_id through the full chain for idempotency
#   3. typical_price is now trusted from matcher output (not zeroed out here)
#
# NO other logic changed.  Drop this file over the original.

import logging
import uuid

from odoo import _, fields, models
from odoo.addons.plasticos_base.models.matching_engine_icp import matching_engine_require_enabled_for_ui
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PlasticosIntakeBuyerMatch(models.Model):
    _inherit = "plasticos.intake"

    match_mode = fields.Selection(
        [
            ("strict", "Strict (all gates hard)"),
            ("relaxed", "Relaxed (polymer only hard)"),
        ],
        string="Match Mode",
        default="strict",
        help="Strict: all 12 gates are hard exclusions. "
        "Relaxed: only polymer is hard, others are soft scoring signals.",
    )

    def action_match_to_buyers(self):
        """Run buyer matching v2.0: facility.profile + Neo4j graph scoring.

        Persists results to both plasticos.intake.match (for UI selection)
        and plasticos.match.result (canonical audit log).
        """
        matching_engine_require_enabled_for_ui(self.env)
        graph_used = False
        neo4j_unavailable_for = []

        for record in self:
            if not record.material_profile_id:
                raise UserError(
                    _(
                        "Intake '%s' has no material profile. Link a material profile before matching.",
                        record.name,
                    )
                )

            run_id = str(uuid.uuid4())
            matcher = self.env["plasticos.buyer.matcher"]
            try:
                matches = matcher.find_matches_for_supplier(
                    supplier_partner_id=record.partner_id.id,
                    intake_id=record.id,
                    max_results=20,
                    mode=record.match_mode or "strict",
                )
            except (UserError, ValidationError):
                raise
            except Exception as exc:
                _logger.warning("Buyer matcher unavailable for intake %s: %s", record.id, exc)
                matches = []
                self._notify_neo4j_fallback(
                    record,
                    _("Buyer matching is currently stubbed/unavailable."),
                )

            _logger.info("Buyer match v2.0 for intake %s: found %d matches", record.name, len(matches))

            # ── Persist to plasticos.intake.match (UI selection layer) ───────
            record.match_line_ids.unlink()
            for m in matches:
                if not m.get("buyer_id"):
                    continue
                self.env["plasticos.intake.match"].create(
                    {
                        "intake_id": record.id,
                        "buyer_id": m.get("buyer_id"),
                        "match_score": (m.get("total_score") or 0.0) * 100,
                        "match_reason": ", ".join(m.get("gates_failed") or []) or "All gates passed",
                        "typical_price": m.get("typical_price") or 0.0,
                    }
                )

            # ── Persist to plasticos.match.result (canonical audit log) ──────
            if "plasticos.match.result.writer" in self.env:
                try:
                    self.env["plasticos.match.result.writer"].persist_match_lines(record, matches, run_id=run_id)
                except Exception as exc:
                    _logger.error("match.result persistence failed for intake %s: %s", record.id, exc)

            if matches:
                record.status = "matched"
                record.message_post(
                    body=f"Matched {len(matches)} buyer(s) via v2.0 engine (run {run_id[:8]}).",
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )

            if "plasticos.graph.service" in self.env:
                cfg = self.env["plasticos.graph.service"]._get_config()
                if cfg.get("uri") and cfg.get("user") and cfg.get("password"):
                    graph_used = True
                else:
                    neo4j_unavailable_for.append(record)
                    self._notify_neo4j_fallback(
                        record,
                        _("Neo4j not configured (set NEO4J_* in .env or System Parameters)."),
                    )
            else:
                neo4j_unavailable_for.append(record)

        act_window = {
            "type": "ir.actions.act_window",
            "name": _("Match Results"),
            "res_model": "plasticos.match.result",
            "view_mode": "list,form",
            "domain": [("intake_id", "in", self.ids)],
            "target": "current",
        }

        if neo4j_unavailable_for and not graph_used:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Neo4j unavailable"),
                    "message": _(
                        "Graph match was skipped. Only deterministic match results are shown. "
                        "Configure NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env or System Parameters."
                    ),
                    "type": "warning",
                    "sticky": False,
                    "next": act_window,
                },
            }
        return act_window

    def _notify_neo4j_fallback(self, intake, reason):
        """Post chatter message when Neo4j was not used for this intake."""
        intake.message_post(
            body=_("Neo4j was not used for this match — only deterministic results are shown. %s") % (reason or ""),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

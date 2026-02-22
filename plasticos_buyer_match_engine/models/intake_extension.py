import logging

from odoo import _, models
from odoo.exceptions import UserError

from ..services.matcher import PlasticosMatcher

_logger = logging.getLogger(__name__)


class PlasticosIntake(models.Model):
    _inherit = "plasticos.intake"

    def action_match_to_buyers(self):
        """Run buyer matching: deterministic matcher + Neo4j graph when available.

        Requires a linked material_profile_id. Results are written to
        plasticos.match.result. If Neo4j is unavailable, only deterministic
        results are used and a notification is shown.
        """
        graph_used = False
        neo4j_unavailable_for = []

        for record in self:
            if not record.material_profile_id:
                raise UserError(
                    _(
                        "Intake '%s' has no material profile. " "Link a material profile before matching.",
                        record.name,
                    )
                )
            matcher = PlasticosMatcher(self.env)
            matcher.match(record)

            if self.env.get("plasticos.graph.service"):
                cfg = self.env["plasticos.graph.service"]._get_config()
                if cfg.get("uri") and cfg.get("user") and cfg.get("password"):
                    try:
                        self.env["plasticos.graph.service"].sudo().match_buyers_for_intake(record)
                        graph_used = True
                    except Exception as exc:
                        _logger.warning(
                            "Neo4j graph match skipped for intake %s: %s",
                            record.id,
                            exc,
                        )
                        neo4j_unavailable_for.append(record)
                        self._notify_neo4j_fallback(record, str(exc))
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

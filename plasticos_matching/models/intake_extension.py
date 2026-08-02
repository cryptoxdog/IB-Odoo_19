"""Intake match action in surviving matching addon (M2 Gate-only path)."""

from odoo import _, models
from odoo.addons.plasticos_base.models.matching_engine_icp import matching_engine_require_enabled_for_ui


class PlasticosIntakeGateMatch(models.Model):
    _inherit = "plasticos.intake"

    def action_match_to_buyers(self):
        """Match buyers via Gate-only orchestrator (no local scoring fallback)."""
        matching_engine_require_enabled_for_ui(self.env)
        orchestrator = self.env["plasticos.match.orchestrator"]
        for record in self:
            run, matches = orchestrator.run_match_for_intake(
                record,
                max_results=20,
                mode=getattr(record, "match_mode", None) or "strict",
            )
            run_id = orchestrator.persist_review_results(record, matches, run)
            if matches:
                record.status = "matched"
                record.message_post(
                    body=_(
                        "Matched %(count)s buyer(s) via Gate (run %(run)s / %(short)s).",
                        count=len(matches),
                        run=run.id,
                        short=run_id[:8],
                    ),
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
            else:
                record.message_post(
                    body=_("Gate match returned zero buyers (run %s).") % run.id,
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Results"),
            "res_model": "plasticos.match.result",
            "view_mode": "list,form",
            "domain": [("intake_id", "in", self.ids)],
            "target": "current",
        }

"""Intake match actions — Gate-only with explicit degraded/retry UX (M3)."""

from odoo import _, models
from odoo.addons.plasticos_base.models.matching_engine_icp import matching_engine_require_enabled_for_ui
from odoo.exceptions import UserError


class PlasticosIntakeGateMatch(models.Model):
    _inherit = "plasticos.intake"

    def action_match_to_buyers(self):
        """Match buyers via Gate-only orchestrator (no local scoring fallback)."""
        matching_engine_require_enabled_for_ui(self.env)
        orchestrator = self.env["plasticos.match.orchestrator"]
        for record in self:
            try:
                run, matches = orchestrator.run_match_for_intake(
                    record,
                    max_results=20,
                    mode=getattr(record, "match_mode", None) or "strict",
                )
            except UserError as exc:
                # Failure already audited on plasticos.match.run — surface to operator.
                record.message_post(
                    body=_("Gate match degraded/failed: %s") % exc,
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
                raise
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

    def action_open_latest_match_run(self):
        """Open the latest match run for operator triage (retryable/failed/degraded)."""
        self.ensure_one()
        run = self.env["plasticos.match.run"].search(
            [("intake_id", "=", self.id)], order="create_date desc, id desc", limit=1
        )
        if not run:
            raise UserError(_("No match runs recorded for this intake."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Run"),
            "res_model": "plasticos.match.run",
            "res_id": run.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_retry_latest_match(self):
        """Retry the latest non-ok Gate match run for this intake."""
        self.ensure_one()
        matching_engine_require_enabled_for_ui(self.env)
        run = self.env["plasticos.match.run"].search(
            [
                ("intake_id", "=", self.id),
                ("state", "in", ("retryable", "failed", "degraded")),
            ],
            order="create_date desc, id desc",
            limit=1,
        )
        if not run:
            raise UserError(_("No retryable/failed/degraded match run found for this intake."))
        return run.action_retry_match()

"""
Web Lead Bulk Action Wizard
Allows bulk conversion, retry, and force-hot actions for multiple web leads.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LeadBulkActionWizard(models.TransientModel):
    _name = "plasticos.web.lead.bulk.action.wizard"
    _description = "Bulk Web Lead Actions"

    action_type = fields.Selection(
        [
            ("force_hot", "Force HOT (Create Intake)"),
            ("retry_triage", "Retry AI Triage"),
            ("mark_skipped", "Mark as Skipped"),
        ],
        string="Action",
        required=True,
        default="force_hot",
    )

    notes = fields.Text(
        string="Notes",
        help="Notes for the action (will be logged in chatter).",
    )

    lead_ids = fields.Many2many(
        "plasticos.web.lead",
        string="Web Leads",
        readonly=True,
    )

    lead_count = fields.Integer(
        compute="_compute_lead_count",
        string="Lead Count",
    )

    # Statistics for display
    hot_count = fields.Integer(
        compute="_compute_stats",
        string="HOT Leads",
    )
    cold_count = fields.Integer(
        compute="_compute_stats",
        string="COLD Leads",
    )
    error_count = fields.Integer(
        compute="_compute_stats",
        string="Error Leads",
    )

    @api.depends("lead_ids")
    def _compute_lead_count(self):
        for rec in self:
            rec.lead_count = len(rec.lead_ids)

    @api.depends("lead_ids")
    def _compute_stats(self):
        for rec in self:
            rec.hot_count = len(rec.lead_ids.filtered(lambda l: l.decision == "hot"))
            rec.cold_count = len(rec.lead_ids.filtered(lambda l: l.decision == "cold"))
            rec.error_count = len(rec.lead_ids.filtered(lambda l: l.state == "error"))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["lead_ids"] = [(6, 0, active_ids)]
        return res

    def action_execute(self):
        """Execute the selected bulk action."""
        self.ensure_one()

        if not self.lead_ids:
            raise UserError(_("No web leads selected."))

        if self.action_type == "force_hot":
            return self._action_force_hot()
        elif self.action_type == "retry_triage":
            return self._action_retry_triage()
        elif self.action_type == "mark_skipped":
            return self._action_mark_skipped()

    def _action_force_hot(self):
        """Force convert COLD leads to HOT and create intakes."""
        valid_leads = self.lead_ids.filtered(lambda l: l.decision == "cold" and not l.intake_id)
        if not valid_leads:
            raise UserError(_("No COLD leads without intake to convert."))

        success_count = 0
        error_leads = []

        for lead in valid_leads:
            try:
                lead.action_force_hot()
                if self.notes:
                    lead.message_post(
                        body=_("Forced to HOT via bulk action<br/>Notes: %s") % self.notes,
                        message_type="notification",
                    )
                success_count += 1
            except Exception as e:
                error_leads.append(f"{lead.lead_id}: {str(e)}")

        message = _("%d lead(s) converted to HOT") % success_count
        if error_leads:
            message += _("\n\nErrors:\n%s") % "\n".join(error_leads[:5])

        return self._return_notification(message)

    def _action_retry_triage(self):
        """Retry AI triage for errored or skipped leads."""
        valid_leads = self.lead_ids.filtered(lambda l: l.state in ("error", "skipped", "received"))
        if not valid_leads:
            raise UserError(_("No leads in error/skipped/received state to retry."))

        success_count = 0
        error_leads = []

        for lead in valid_leads:
            try:
                lead.action_retry_triage()
                if self.notes:
                    lead.message_post(
                        body=_("AI Triage retried via bulk action<br/>Notes: %s") % self.notes,
                        message_type="notification",
                    )
                success_count += 1
            except Exception as e:
                error_leads.append(f"{lead.lead_id}: {str(e)}")

        message = _("%d lead(s) re-triaged") % success_count
        if error_leads:
            message += _("\n\nErrors:\n%s") % "\n".join(error_leads[:5])

        return self._return_notification(message)

    def _action_mark_skipped(self):
        """Mark leads as skipped (COLD archive)."""
        valid_leads = self.lead_ids.filtered(lambda l: l.state not in ("intake_created",))
        if not valid_leads:
            raise UserError(_("No leads available to skip."))

        for lead in valid_leads:
            lead.write(
                {
                    "state": "skipped",
                    "decision": "cold",
                }
            )
            if self.notes:
                lead.message_post(
                    body=_("Marked as skipped via bulk action<br/>Notes: %s") % self.notes,
                    message_type="notification",
                )

        return self._return_notification(_("%d lead(s) marked as skipped") % len(valid_leads))

    def _return_notification(self, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Action Complete"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

"""
Claim Bulk Update Wizard
Allows bulk status updates and assignment for multiple claims from list view.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ClaimBulkUpdateWizard(models.TransientModel):
    _name = "plasticos.claim.bulk.update.wizard"
    _description = "Bulk Update Claim Status"

    action_type = fields.Selection(
        [
            ("status", "Change Status"),
            ("assign", "Assign To User"),
            ("escalate", "Escalate"),
        ],
        string="Action",
        required=True,
        default="status",
    )

    new_state = fields.Selection(
        [
            ("pending", "Pending Review"),
            ("in_progress", "In Progress"),
            ("escalated", "Escalated"),
            ("resolved", "Resolved"),
            ("archived", "Archived"),
        ],
        string="New Status",
    )

    assignee_id = fields.Many2one(
        "res.users",
        string="Assign To",
    )

    escalation_reason = fields.Text(
        string="Escalation Reason",
    )

    resolution_note = fields.Text(
        string="Resolution Note",
        help="Required when resolving claims.",
    )

    reason = fields.Text(
        string="Reason",
        required=True,
        help="Reason for the bulk action (will be logged in chatter).",
    )

    claim_ids = fields.Many2many(
        "plasticos.claim",
        string="Claims",
        readonly=True,
    )

    claim_count = fields.Integer(
        compute="_compute_claim_count",
        string="Claim Count",
    )

    @api.depends("claim_ids")
    def _compute_claim_count(self):
        for rec in self:
            rec.claim_count = len(rec.claim_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["claim_ids"] = [(6, 0, active_ids)]
        return res

    def action_execute(self):
        """Execute the selected bulk action."""
        self.ensure_one()

        if not self.claim_ids:
            raise UserError(_("No claims selected."))

        if self.action_type == "status":
            return self._action_change_status()
        elif self.action_type == "assign":
            return self._action_assign()
        elif self.action_type == "escalate":
            return self._action_escalate()

    def _action_change_status(self):
        """Change status of all selected claims."""
        if not self.new_state:
            raise UserError(_("Please select a new status."))

        if self.new_state == "resolved" and not self.resolution_note:
            raise UserError(_("Resolution note is required when resolving claims."))

        updated_count = 0
        for claim in self.claim_ids:
            if claim.state == "archived" and self.new_state != "in_progress":
                continue

            old_state = claim.state
            vals = {"state": self.new_state}

            if self.new_state == "resolved":
                vals["resolution_note"] = self.resolution_note
                vals["resolved_at"] = fields.Datetime.now()

            claim.write(vals)
            claim.message_post(
                body=_(
                    "Status changed from <b>%(old)s</b> to <b>%(new)s</b><br/>"
                    "Reason: %(reason)s<br/>"
                    "Updated by: %(user)s (Bulk Update)"
                )
                % {
                    "old": old_state,
                    "new": self.new_state,
                    "reason": self.reason,
                    "user": self.env.user.name,
                },
                message_type="notification",
            )
            updated_count += 1

        return self._return_notification(_("%d claim(s) updated to '%s'") % (updated_count, self.new_state))

    def _action_assign(self):
        """Assign all selected claims to a user."""
        if not self.assignee_id:
            raise UserError(_("Please select a user to assign to."))

        updated_count = 0
        for claim in self.claim_ids:
            old_assignee = claim.assignee_id.name or "Unassigned"
            claim.write({"assignee_id": self.assignee_id.id})
            claim.message_post(
                body=_(
                    "Assigned from <b>%(old)s</b> to <b>%(new)s</b><br/>"
                    "Reason: %(reason)s<br/>"
                    "Updated by: %(user)s (Bulk Update)"
                )
                % {
                    "old": old_assignee,
                    "new": self.assignee_id.name,
                    "reason": self.reason,
                    "user": self.env.user.name,
                },
                message_type="notification",
            )
            updated_count += 1

        return self._return_notification(_("%d claim(s) assigned to '%s'") % (updated_count, self.assignee_id.name))

    def _action_escalate(self):
        """Escalate all selected claims."""
        if not self.escalation_reason:
            raise UserError(_("Please provide an escalation reason."))

        updated_count = 0
        for claim in self.claim_ids:
            if claim.state in ("resolved", "archived"):
                continue
            claim.action_escalate(
                reason=self.escalation_reason,
                escalate_to=self.assignee_id if self.assignee_id else None,
            )
            claim.message_post(
                body=_("Escalated via bulk action<br/>Reason: %(reason)s<br/>Updated by: %(user)s")
                % {
                    "reason": self.escalation_reason,
                    "user": self.env.user.name,
                },
                message_type="notification",
            )
            updated_count += 1

        return self._return_notification(_("%d claim(s) escalated") % updated_count)

    def _return_notification(self, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Update Complete"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

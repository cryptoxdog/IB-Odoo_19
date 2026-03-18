"""
Load Bulk Update Wizard
Allows bulk status updates for multiple logistics loads from list view.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class LoadBulkUpdateWizard(models.TransientModel):
    _name = "plasticos.load.bulk.update.wizard"
    _description = "Bulk Update Load Status"

    new_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("awaiting_ready", "Awaiting Ready"),
            ("ready_confirmed", "Ready Confirmed"),
            ("rate_confirmed", "Rate Confirmed"),
            ("scheduled", "Scheduled"),
            ("dispatched", "Dispatched"),
            ("picked_up", "Picked Up"),
            ("delivered", "Delivered"),
            ("closed", "Closed"),
            ("exception", "Exception"),
        ],
        string="New Status",
        required=True,
    )

    reason = fields.Text(
        string="Reason",
        required=True,
        help="Reason for the status change (will be logged in chatter).",
    )

    load_ids = fields.Many2many(
        "plasticos.load",
        string="Loads",
        readonly=True,
    )

    load_count = fields.Integer(
        compute="_compute_load_count",
        string="Load Count",
    )

    @api.depends("load_ids")
    def _compute_load_count(self):
        for rec in self:
            rec.load_count = len(rec.load_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["load_ids"] = [(6, 0, active_ids)]
        return res

    def action_update_status(self):
        """Apply the status update to all selected loads using state machine."""
        self.ensure_one()

        if not self.load_ids:
            raise UserError(_("No loads selected."))

        errors = []
        updated_count = 0
        for load in self.load_ids:
            old_state = load.state
            try:
                load._transition(self.new_state)
                load.message_post(
                    body=_(
                        "Status changed from <b>%(old)s</b> to <b>%(new)s</b><br/>"
                        "Reason: %(reason)s<br/>Updated by: %(user)s (Bulk Update)"
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
            except (UserError, ValidationError) as e:
                errors.append(f"{load.name}: {e.args[0]}")

        if errors:
            raise UserError(_("Some loads could not be updated:\n%s") % "\n".join(errors[:10]))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Update Complete"),
                "message": _("%d load(s) updated to '%s'") % (updated_count, self.new_state),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

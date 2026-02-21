"""
Load Bulk Update Wizard
Allows bulk status updates for multiple logistics loads from list view.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        """Apply the status update to all selected loads."""
        self.ensure_one()

        if not self.load_ids:
            raise UserError(_("No loads selected."))

        # Validate transitions
        invalid = []
        for load in self.load_ids:
            if load.state == "closed" and self.new_state != "exception":
                invalid.append(f"{load.name}: Cannot change status of closed load")
            elif load.state in ("dispatched", "picked_up", "delivered") and self.new_state in (
                "draft",
                "awaiting_ready",
            ):
                invalid.append(f"{load.name}: Cannot revert dispatched load to early state")

        if invalid:
            raise UserError(_("Invalid transitions:\n%s") % "\n".join(invalid[:5]))

        updated_count = 0
        for load in self.load_ids:
            old_state = load.state

            vals = {
                "state": self.new_state,
                "entered_state_at": fields.Datetime.now(),
            }
            if self.new_state == "dispatched":
                vals["dispatched_at"] = fields.Datetime.now()
            elif self.new_state == "delivered":
                vals["delivered_at"] = fields.Datetime.now()

            # Use SQL to bypass write() restrictions for bulk operations
            self.env.cr.execute(
                """
                UPDATE plasticos_load
                SET state = %s, entered_state_at = %s
                WHERE id = %s
                """,
                (self.new_state, fields.Datetime.now(), load.id),
            )
            load.invalidate_recordset(["state", "entered_state_at"])

            load.message_post(
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

"""
Transaction Bulk Update Wizard
Allows bulk status updates for multiple transactions from list view.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TransactionBulkUpdateWizard(models.TransientModel):
    _name = "plasticos.tx.bulk.wizard"
    _description = "Bulk Update Transaction Status"

    new_state = fields.Selection(
        [
            ("active", "Active"),
            ("pending_supplier", "Pending Supplier"),
            ("supplier_ready", "Supplier Ready"),
            ("in_progress", "In Progress"),
            ("in_transit", "In Transit"),
            ("delivered", "Delivered"),
            ("invoiced", "Invoiced"),
            ("cancelled", "Cancelled"),
        ],
        string="New Status",
        required=True,
    )

    reason = fields.Text(
        string="Reason",
        required=True,
        help="Reason for the status change (will be logged in chatter).",
    )

    transaction_ids = fields.Many2many(
        "plasticos.transaction",
        string="Transactions",
        readonly=True,
    )

    transaction_count = fields.Integer(
        compute="_compute_transaction_count",
        string="Transaction Count",
    )

    @api.depends("transaction_ids")
    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)

    @api.model
    def default_get(self, fields_list):
        """Load selected transactions from context."""
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["transaction_ids"] = [(6, 0, active_ids)]
        return res

    def action_update_status(self):
        """Apply the status update to all selected transactions."""
        self.ensure_one()

        if not self.transaction_ids:
            raise UserError(_("No transactions selected."))

        # Validate state transitions
        invalid_transitions = []
        for tx in self.transaction_ids:
            if tx.state == "closed":
                invalid_transitions.append(f"{tx.name}: Cannot change status of closed transaction")
            elif tx.state == "cancelled" and self.new_state != "draft":
                invalid_transitions.append(f"{tx.name}: Cancelled transactions can only be reopened as Draft")

        if invalid_transitions:
            raise UserError(_("Invalid state transitions:\n%s") % "\n".join(invalid_transitions))

        # Apply updates with audit trail
        updated_count = 0
        for tx in self.transaction_ids:
            old_state = tx.state
            # Use ORM with bypass_state_guard context (same pattern as action_mark_* methods)
            # This ensures @api.depends recomputes, base.automation triggers, and tracking fire correctly
            tx.with_context(bypass_state_guard=True).write({"state": self.new_state})

            # Log to chatter
            tx.message_post(
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
                "message": _("%d transaction(s) updated to '%s'") % (updated_count, self.new_state),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

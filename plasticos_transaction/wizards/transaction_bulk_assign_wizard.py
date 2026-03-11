"""
Transaction Bulk Assign Wizard
Bulk assign suppliers/buyers to multiple transactions at once.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TransactionBulkAssignWizard(models.TransientModel):
    _name = "plasticos.transaction.bulk.assign.wizard"
    _description = "Bulk Assign Partners to Transactions"

    action_type = fields.Selection(
        [
            ("assign_supplier", "Assign Supplier"),
            ("assign_buyer", "Assign Buyer"),
            ("assign_both", "Assign Both Supplier & Buyer"),
        ],
        string="Action",
        required=True,
        default="assign_supplier",
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        domain=[("is_company", "=", True)],
        help="Select the supplier company to assign.",
    )
    buyer_id = fields.Many2one(
        "res.partner",
        string="Buyer",
        domain=[("is_company", "=", True)],
        help="Select the buyer company to assign.",
    )

    reason = fields.Text(
        string="Reason",
        required=True,
        help="Reason for the bulk assignment (will be logged in chatter).",
    )

    transaction_ids = fields.Many2many(
        "plasticos.transaction",
        relation="tx_bulk_assign_wiz_rel",
        column1="wizard_id",
        column2="transaction_id",
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
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["transaction_ids"] = [(6, 0, active_ids)]
        return res

    def action_execute(self):
        """Execute the bulk partner assignment."""
        self.ensure_one()
        self._validate_execute_inputs()

        updated = 0
        for tx in self.transaction_ids:
            if self._apply_partner_changes(tx):
                updated += 1

        return self._return_notification(_("%d transaction(s) updated with partner assignments") % updated)

    def _validate_execute_inputs(self):
        """Raise UserError if required selections are missing for the chosen action type."""
        if not self.transaction_ids:
            raise UserError(_("No transactions selected."))
        if self.action_type in ("assign_supplier", "assign_both") and not self.supplier_id:
            raise UserError(_("Please select a supplier."))
        if self.action_type in ("assign_buyer", "assign_both") and not self.buyer_id:
            raise UserError(_("Please select a buyer."))

    def _build_partner_vals(self, tx):
        """Build (vals, changes) for the partner fields being assigned on this transaction."""
        changes = []
        vals = {}
        if self.action_type in ("assign_supplier", "assign_both"):
            old_supplier = tx.supplier_id.name if tx.supplier_id else "None"
            vals["supplier_id"] = self.supplier_id.id
            changes.append(_("Supplier: %(old)s → %(new)s") % {"old": old_supplier, "new": self.supplier_id.name})
        if self.action_type in ("assign_buyer", "assign_both"):
            old_buyer = tx.buyer_id.name if tx.buyer_id else "None"
            vals["buyer_id"] = self.buyer_id.id
            changes.append(_("Buyer: %(old)s → %(new)s") % {"old": old_buyer, "new": self.buyer_id.name})
        return vals, changes

    def _apply_partner_changes(self, tx):
        """Write partner vals and post chatter message; return True if any change was applied."""
        vals, changes = self._build_partner_vals(tx)
        if not vals:
            return False
        tx.write(vals)
        tx.message_post(
            body=_(
                "Partner assignment updated:<br/>%(changes)s<br/>"
                "Reason: %(reason)s<br/>"
                "Updated by: %(user)s (Bulk Assign)"
            )
            % {
                "changes": "<br/>".join(changes),
                "reason": self.reason,
                "user": self.env.user.name,
            },
            message_type="notification",
        )
        return True

    def _return_notification(self, message):
        """Return a notification action."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Assignment Complete"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

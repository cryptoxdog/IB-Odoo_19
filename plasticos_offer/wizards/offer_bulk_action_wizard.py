"""
Offer Bulk Action Wizard
Allows bulk accept/reject/send for multiple offers from list view.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OfferBulkActionWizard(models.TransientModel):
    _name = "plasticos.offer.bulk.action.wizard"
    _description = "Bulk Offer Actions"

    action_type = fields.Selection(
        [
            ("send", "Send Offers"),
            ("accept", "Accept Offers"),
            ("reject", "Reject Offers"),
            ("cancel", "Cancel Offers"),
        ],
        string="Action",
        required=True,
        default="send",
    )

    rejection_reason = fields.Text(
        string="Rejection Reason",
        help="Required when rejecting offers.",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional notes (will be logged in chatter).",
    )

    offer_ids = fields.Many2many(
        "plasticos.offer",
        string="Offers",
        readonly=True,
    )

    offer_count = fields.Integer(
        compute="_compute_offer_count",
        string="Offer Count",
    )

    @api.depends("offer_ids")
    def _compute_offer_count(self):
        for rec in self:
            rec.offer_count = len(rec.offer_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["offer_ids"] = [(6, 0, active_ids)]
        return res

    def action_execute(self):
        """Execute the selected bulk action."""
        self.ensure_one()

        if not self.offer_ids:
            raise UserError(_("No offers selected."))

        if self.action_type == "send":
            return self._action_send()
        elif self.action_type == "accept":
            return self._action_accept()
        elif self.action_type == "reject":
            return self._action_reject()
        elif self.action_type == "cancel":
            return self._action_cancel()

    def _action_send(self):
        """Send all draft offers."""
        valid_offers = self.offer_ids.filtered(lambda o: o.state == "draft")
        if not valid_offers:
            raise UserError(_("No draft offers to send."))

        for offer in valid_offers:
            offer.action_send()
            if self.notes:
                offer.message_post(
                    body=_("Sent via bulk action<br/>Notes: %s") % self.notes,
                    message_type="notification",
                )

        return self._return_notification(_("%d offer(s) sent") % len(valid_offers))

    def _action_accept(self):
        """Accept all sent/responded offers."""
        valid_offers = self.offer_ids.filtered(lambda o: o.state in ("sent", "responded"))
        if not valid_offers:
            raise UserError(_("No offers in sent/responded state to accept."))

        for offer in valid_offers:
            offer.action_accept()
            if self.notes:
                offer.message_post(
                    body=_("Accepted via bulk action<br/>Notes: %s") % self.notes,
                    message_type="notification",
                )

        return self._return_notification(_("%d offer(s) accepted") % len(valid_offers))

    def _action_reject(self):
        """Reject all non-accepted/cancelled offers."""
        if not self.rejection_reason:
            raise UserError(_("Please provide a rejection reason."))

        valid_offers = self.offer_ids.filtered(lambda o: o.state not in ("accepted", "cancelled"))
        if not valid_offers:
            raise UserError(_("No offers available to reject."))

        for offer in valid_offers:
            offer.write({"rejection_reason": self.rejection_reason})
            offer.action_reject()
            offer.message_post(
                body=_("Rejected via bulk action<br/>Reason: %(reason)s") % {"reason": self.rejection_reason},
                message_type="notification",
            )

        return self._return_notification(_("%d offer(s) rejected") % len(valid_offers))

    def _action_cancel(self):
        """Cancel all non-accepted offers."""
        valid_offers = self.offer_ids.filtered(lambda o: o.state != "accepted")
        if not valid_offers:
            raise UserError(_("No offers available to cancel."))

        for offer in valid_offers:
            offer.action_cancel()
            if self.notes:
                offer.message_post(
                    body=_("Cancelled via bulk action<br/>Notes: %s") % self.notes,
                    message_type="notification",
                )

        return self._return_notification(_("%d offer(s) cancelled") % len(valid_offers))

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

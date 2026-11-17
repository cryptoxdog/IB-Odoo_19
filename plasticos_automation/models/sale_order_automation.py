import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_APPOINTMENT_ACTIVITY = "Request delivery appointment"
_LOGISTICS_GROUP = "plasticos_security_base.group_logistics"


class SaleOrderAutomation(models.Model):
    _inherit = "sale.order"

    # ── Delivery dock rule (ADR-135 §3) ────────────────────────────
    delivery_term = fields.Selection(
        [
            ("fcfs", "FCFS (First Come, First Served)"),
            ("appointment", "Appointment Required"),
        ],
        string="Delivery Dock Rule",
        default="appointment",
        help=(
            "Delivery-side dock rule. Defaults from the ship-to site, "
            "then that site's commercial company, then Appointment."
        ),
    )
    appointment_requested = fields.Boolean(
        string="Dock Appointment Requested",
        default=False,
        help="Set when a person sends the delivery appointment request. Confirmation does not set it.",
    )
    appointment_requested_on = fields.Datetime(
        string="Dock Appointment Requested On",
        help="Timestamp when dock appointment was requested.",
    )

    def _dock_rule_for_partner(self, partner) -> str:
        from odoo.addons.plasticos_transaction.dock_rule import rule_from_site_then_company

        if not partner:
            return "appointment"
        commercial = partner.commercial_partner_id or partner
        is_site = bool(partner._plasticos_is_site())
        return rule_from_site_then_company(
            partner.default_delivery_term if is_site else None,
            commercial.default_delivery_term,
            partner_is_site=is_site,
        )

    def _fill_delivery_dock_rule(self, vals):
        if "delivery_term" in vals:
            return
        partner_id = vals.get("partner_shipping_id") or vals.get("partner_id")
        partner = self.env["res.partner"].browse(partner_id) if partner_id else self.env["res.partner"]
        vals["delivery_term"] = self._dock_rule_for_partner(partner)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._fill_delivery_dock_rule(vals)
        return super().create(vals_list)

    @api.onchange("partner_shipping_id", "partner_id")
    def _onchange_delivery_dock_rule(self):
        for order in self:
            order.delivery_term = order._dock_rule_for_partner(order.partner_shipping_id or order.partner_id)

    def _plasticos_logistics_activity_user(self):
        """One active internal user in the Logistics group, stable by id."""
        self.ensure_one()
        group = self.env.ref(_LOGISTICS_GROUP, raise_if_not_found=False)
        if not group:
            return self.env.user
        users = self.env["res.users"].search(
            [("group_ids", "in", group.id), ("share", "=", False), ("active", "=", True)],
            order="id",
        )
        if self.company_id:
            scoped = users.filtered(lambda user: self.company_id in user.company_ids)
            if scoped:
                users = scoped
        return users[:1] or self.env.user

    def _plasticos_request_delivery_appointment_activity(self):
        """One Logistics activity per confirmed Appointment order. No mail, no flag.

        ADR-135 §4. The activity names the delivery site and leaves the expected
        ready date blank (that date belongs to scheduling, not this step).
        ``appointment_requested`` stays untouched. A second call finds the open
        activity and does not create another. sudo on the search: the activity
        is assigned to Logistics, and the confirming user may not be able to read it.
        """
        summary = _APPOINTMENT_ACTIVITY
        orders = self.filtered(lambda order: order.state == "sale" and order.delivery_term == "appointment")
        if not orders:
            return self.env["mail.activity"]
        existing = (
            self.env["mail.activity"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "sale.order"),
                    ("res_id", "in", orders.ids),
                    ("summary", "=", summary),
                ]
            )
        )
        already = set(existing.mapped("res_id"))
        created = self.env["mail.activity"]
        for order in orders:
            if order.id in already:
                continue
            site = order.partner_shipping_id or order.partner_id
            site_name = site.display_name if site else ""
            note = f"Delivery site: {site_name}\nExpected ready date: "
            scheduled = order.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=order._plasticos_logistics_activity_user().id,
                summary=summary,
                note=note,
            )
            if scheduled:
                created |= scheduled
            already.add(order.id)
        return created

    def action_request_dock_appointment(self):
        """Mark the order as having a dock appointment requested."""
        for rec in self:
            rec.appointment_requested = True
            rec.appointment_requested_on = fields.Datetime.now()
            rec.message_post(
                body=f"Dock appointment requested for SO {rec.name}.",
                message_type="notification",
            )
            _logger.info(
                "Logistics automation: dock appointment requested for SO %s",
                rec.name,
            )

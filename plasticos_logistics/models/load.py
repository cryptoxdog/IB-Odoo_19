import logging

from odoo import api, fields, models
from odoo.addons.plasticos_logistics.services.state_machine import VALID_TRANSITIONS, new_correlation_id
from odoo.exceptions import UserError, ValidationError

RES_PARTNER = "res.partner"
PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_LOAD = "plasticos.load"
_logger = logging.getLogger(__name__)


class PlasticosLoad(models.Model):
    _name = "plasticos.load"
    _description = "Plasticos Logistics Load"
    _inherit = ["mail.thread"]

    name = fields.Char(
        required=True, default=lambda self: self.env["ir.sequence"].next_by_code(PLASTICOS_LOAD) or "New"
    )
    sale_order_id = fields.Many2one("sale.order")
    carrier_id = fields.Many2one(RES_PARTNER, string="Carrier")
    rate_amount = fields.Float(string="Rate Amount")
    rate_confirmed_at = fields.Datetime()
    rate_auto_reused = fields.Boolean(default=False)

    ready_confirmed_by = fields.Char()
    ready_confirmed_at = fields.Datetime()

    pickup_datetime = fields.Datetime(string="Pickup Date/Time")
    delivery_datetime = fields.Datetime(string="Delivery Date/Time")

    bol_pickup_attached = fields.Boolean(default=False)
    bol_delivery_attached = fields.Boolean(default=False)

    entered_state_at = fields.Datetime(default=fields.Datetime.now, index=True)
    sla_breached = fields.Boolean(default=False, index=True)
    dispatched_at = fields.Datetime()
    delivered_at = fields.Datetime()
    cycle_time_hours = fields.Float(compute="_compute_cycle_time", store=True, index=True)

    # ── Reverse Link to Transaction (for UX) ──────────────────────────
    transaction_id = fields.Many2one(
        PLASTICOS_TRANSACTION,
        string="Transaction",
        compute="_compute_transaction_id",
        store=False,
        help="Transaction linked to this load (reverse lookup).",
    )

    # ── Pickup Location Fields ──────────────────────────────────────
    pickup_partner_id = fields.Many2one(RES_PARTNER, string="Pickup Location", help="Shipper/pickup location for BOL")
    pickup_contact_name = fields.Char(string="Pickup Contact")
    pickup_contact_phone = fields.Char(string="Pickup Phone")
    pickup_contact_mobile = fields.Char(string="Pickup Mobile")
    pickup_reference = fields.Char(string="Pickup Reference/PO#")
    pickup_hours = fields.Char(string="Pickup Hours", default="M-F: CALL FOR APPOINTMENT")
    pickup_instructions = fields.Text(string="Pickup Instructions")

    # ── Delivery Location Fields ────────────────────────────────────
    delivery_partner_id = fields.Many2one(
        RES_PARTNER, string="Delivery Location", help="Consignee/delivery location for BOL"
    )
    delivery_contact_name = fields.Char(string="Delivery Contact")
    delivery_contact_phone = fields.Char(string="Delivery Phone")
    delivery_contact_mobile = fields.Char(string="Delivery Mobile")
    delivery_reference = fields.Char(string="Delivery Reference/PO#")
    delivery_hours = fields.Char(string="Delivery Hours", default="M-F: 9:00 AM - 3:00 PM")
    delivery_instructions = fields.Text(string="Delivery Instructions")

    # ── Carrier/Transport Fields ────────────────────────────────────
    carrier_contact_name = fields.Char(string="Carrier Contact")
    carrier_contact_phone = fields.Char(string="Carrier Phone")
    trailer_number = fields.Char(string="Trailer Number")
    seal_number = fields.Char(string="Seal Number")

    # ── Cargo/Product Fields ────────────────────────────────────────
    product_description = fields.Char(string="Product Description")
    quantity = fields.Float(string="Quantity", default=1.0)
    quantity_uom = fields.Char(string="Unit", default="Each")
    reference_weight = fields.Float(string="Reference Weight (lbs)")

    # ── Document Control ────────────────────────────────────────────
    double_blind = fields.Boolean(string="Double Blind", default=True)
    straps_bars_needed = fields.Boolean(string="Straps/Bars Needed", default=True)
    notes = fields.Text(string="Notes/Comments")

    state = fields.Selection(
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
        default="draft",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create load and auto-link to transaction via sale_order_id.

        Auto-link only happens if the transaction has both supplier and buyer set.
        This enforces the workflow requirement that loads cannot be assigned until
        the transaction has complete partner information.
        """
        records = super().create(vals_list)
        for rec in records:
            if rec.sale_order_id:
                tx = self.env[PLASTICOS_TRANSACTION].search([("sale_order_id", "=", rec.sale_order_id.id)], limit=1)
                if tx and not tx.load_id and tx.supplier_id and tx.buyer_id:
                    tx.load_id = rec.id
        return records

    def write(self, vals):
        """Guard against unauthorized modifications after dispatch.

        After dispatch, only specific fields can be modified:
        - BOL attachments (pickup/delivery confirmation)
        - State transitions (via action methods)
        - Timestamps (entered_state_at, dispatched_at, delivered_at)
        - Computed fields (cycle_time_hours)
        - Cron-managed fields (sla_breached)
        - Chatter fields (message_ids, message_follower_ids)
        """
        for rec in self:
            if rec.state in ["dispatched", "picked_up", "delivered", "closed"]:
                allowed = {
                    "bol_pickup_attached",
                    "bol_delivery_attached",
                    "state",
                    "entered_state_at",
                    "dispatched_at",
                    "delivered_at",
                    "cycle_time_hours",
                    "sla_breached",
                    "message_ids",
                    "message_follower_ids",
                }
                blocked = set(vals.keys()) - allowed
                if blocked:
                    raise UserError(f"Load locked after dispatch. Cannot modify: {', '.join(sorted(blocked))}")

        res = super().write(vals)

        if "state" in vals and vals["state"] == "closed":
            for rec in self:
                tx = self.env[PLASTICOS_TRANSACTION].search([("load_id", "=", rec.id)], limit=1)
                if tx:
                    tx.message_post(body="Logistics closed.")

        return res

    @api.depends("dispatched_at", "delivered_at")
    def _compute_cycle_time(self):
        for rec in self:
            if rec.dispatched_at and rec.delivered_at:
                delta = (rec.delivered_at - rec.dispatched_at).total_seconds() / 3600
                rec.cycle_time_hours = delta
            else:
                rec.cycle_time_hours = 0

    def _compute_transaction_id(self):
        """Reverse lookup: find transaction that references this load.

        Batched query to avoid N+1 problem on list views.
        Note: No @api.depends() needed for store=False computed fields.
        """
        txs = self.env[PLASTICOS_TRANSACTION].search([("load_id", "in", self.ids)])
        tx_map = {tx.load_id.id: tx.id for tx in txs}
        for rec in self:
            rec.transaction_id = tx_map.get(rec.id, False)

    def action_confirm_ready(self):
        """Confirm load is ready for pickup. Captures authenticated user."""
        for rec in self:
            rec.ready_confirmed_by = self.env.user.name
            rec.ready_confirmed_at = fields.Datetime.now()
            rec._transition("ready_confirmed")

    def action_confirm_rate(self, rate):
        """Confirm carrier rate. Only stores rate memory if lane key is valid."""
        for rec in self:
            rec.rate_amount = rate
            rec.rate_confirmed_at = fields.Datetime.now()
            rec.rate_auto_reused = False
            rec._transition("rate_confirmed")
            if rec.sale_order_id and rec.carrier_id:
                ship = rec.sale_order_id.partner_shipping_id.id
                inv = rec.sale_order_id.partner_invoice_id.id
                if ship and inv:
                    rec._store_rate_memory()
                else:
                    _logger.warning(
                        "Load %s: rate memory skipped — SO %s has no shipping/invoice partner.",
                        rec.id,
                        rec.sale_order_id.name,
                    )

    def action_schedule(self, pickup_dt, delivery_dt):
        for rec in self:
            rec.pickup_datetime = pickup_dt
            rec.delivery_datetime = delivery_dt
            rec._transition("scheduled")

    def action_dispatch(self):
        """Dispatch load to carrier. Validates required fields before dispatch."""
        for rec in self:
            if rec.state != "scheduled":
                raise UserError(f"Load {rec.name} must be in Scheduled state before dispatch.")
            if not rec.carrier_id:
                raise UserError(f"Load {rec.name}: Carrier is required before dispatch.")
            if not rec.pickup_partner_id:
                raise UserError(f"Load {rec.name}: Pickup location is required before dispatch.")
            if not rec.delivery_partner_id:
                raise UserError(f"Load {rec.name}: Delivery location is required before dispatch.")
            if not rec.pickup_datetime:
                raise UserError(f"Load {rec.name}: Pickup date/time is required before dispatch.")
            rec._transition("dispatched")

    def action_close(self):
        for rec in self:
            if not rec.bol_pickup_attached or not rec.bol_delivery_attached:
                raise UserError("BOL documents required.")
            rec._transition("closed")

    def _transition(self, new_state):
        """Transition load to new state with validation.

        Enforces forward-only state machine defined in VALID_TRANSITIONS.
        """
        for rec in self:
            allowed = VALID_TRANSITIONS.get(rec.state, [])
            if new_state not in allowed:
                raise UserError(
                    f"Cannot move load '{rec.name}' from '{rec.state}' to '{new_state}'. "
                    f"Allowed: {allowed or ['none — terminal state']}."
                )

            correlation_id = new_correlation_id()
            old = rec.state
            vals = {"state": new_state, "entered_state_at": fields.Datetime.now()}
            if new_state == "dispatched":
                vals["dispatched_at"] = fields.Datetime.now()
            if new_state == "delivered":
                vals["delivered_at"] = fields.Datetime.now()
            rec.write(vals)
            _logger.info("Load %s state transition: %s -> %s (correlation: %s)", rec.id, old, new_state, correlation_id)

    def _store_rate_memory(self):
        if "plasticos.rate.memory" not in self.env:
            _logger.warning("plasticos.rate.memory model not found; skipping rate memory storage.")
            return
        self.env["plasticos.rate.memory"].create(
            {
                "carrier_id": self.carrier_id.id,
                "lane_key": self._lane_key(),
                "rate_amount": self.rate_amount,
                "rate_date": fields.Date.today(),
            }
        )

    def _lane_key(self):
        so = self.sale_order_id
        return f"{so.partner_shipping_id.id}-{so.partner_invoice_id.id}"

    @api.constrains("pickup_datetime", "delivery_datetime")
    def _check_datetime_order(self):
        """Ensure delivery date/time is not before pickup date/time."""
        for rec in self:
            if rec.pickup_datetime and rec.delivery_datetime:
                if rec.delivery_datetime < rec.pickup_datetime:
                    raise ValidationError(f"Load {rec.name}: Delivery date/time cannot be before pickup date/time.")

    def _cron_escalation_check(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_logistics.cron_escalation_check"])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping escalation cron: lock is already held.")
            return

        try:
            try:
                from odoo.addons.plasticos_logistics.services.escalation_engine import check_escalations

                check_escalations(self.env)
            except ImportError:
                _logger.warning("escalation_engine not found; skipping cron.")
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_logistics.cron_escalation_check"]
            )

    # ── Email Send Actions (Paperless) ──────────────────────────────

    def action_send_delivery_order(self):
        """Open email composer with Delivery Order attached."""
        self.ensure_one()
        template = self._get_email_template("email_template_delivery_order")
        return self._open_mail_composer(template)

    def action_send_bol_pickup(self):
        """Open email composer with BOL Pickup attached."""
        self.ensure_one()
        template = self._get_email_template("email_template_bol_pickup")
        return self._open_mail_composer(template)

    def action_send_bol_delivery(self):
        """Open email composer with BOL Delivery attached."""
        self.ensure_one()
        template = self._get_email_template("email_template_bol_delivery")
        return self._open_mail_composer(template)

    def action_send_dispatch_packet(self):
        """Open email composer with full dispatch packet (all 3 docs)."""
        self.ensure_one()
        template = self._get_email_template("email_template_dispatch_packet")
        return self._open_mail_composer(template)

    def _get_email_template(self, template_name):
        """Get email template from plasticos_automation module.

        Raises ValidationError with clear message if template not found
        (plasticos_automation module not installed).
        """
        xml_id = f"plasticos_automation.{template_name}"
        template = self.env.ref(xml_id, raise_if_not_found=False)
        if not template:
            raise ValidationError(
                f"Email template '{template_name}' not found.\n\n"
                "The plasticos_automation module must be installed to use "
                "email send actions. Please install it from Apps."
            )
        return template

    def _open_mail_composer(self, template):
        """Helper to open mail composer wizard with template."""
        ctx = {
            "default_model": PLASTICOS_LOAD,
            "default_res_ids": self.ids,
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
            "force_email": True,
        }
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    # ═════════════════════════════════════════════════════════
    # Action Methods (for UX smart buttons)
    # ═════════════════════════════════════════════════════════

    def action_view_transaction(self):
        """Open the linked transaction form."""
        self.ensure_one()
        tx = self.env[PLASTICOS_TRANSACTION].search([("load_id", "=", self.id)], limit=1)
        if not tx:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": PLASTICOS_TRANSACTION,
            "res_id": tx.id,
            "view_mode": "form",
            "target": "current",
        }

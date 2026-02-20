from odoo import models, fields, api
from odoo.exceptions import UserError
import uuid
import logging

_logger = logging.getLogger(__name__)

# Stub for l9_trace (enable when module available)
# from odoo.addons.l9_trace.services.trace_kernel import TraceKernel
# from odoo.addons.l9_trace.services.correlation import new_correlation_id

def new_correlation_id():
    """Generate correlation ID (stub for l9_trace)"""
    return str(uuid.uuid4())


class PlasticosLoad(models.Model):
    _name = "plasticos.load"
    _description = "Plasticos Logistics Load"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    sale_order_id = fields.Many2one("sale.order", required=True)
    carrier_id = fields.Many2one("res.partner", string="Carrier")
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

    # ── Pickup Location Fields ──────────────────────────────────────
    pickup_partner_id = fields.Many2one(
        "res.partner", string="Pickup Location",
        help="Shipper/pickup location for BOL"
    )
    pickup_contact_name = fields.Char(string="Pickup Contact")
    pickup_contact_phone = fields.Char(string="Pickup Phone")
    pickup_contact_mobile = fields.Char(string="Pickup Mobile")
    pickup_reference = fields.Char(string="Pickup Reference/PO#")
    pickup_hours = fields.Char(string="Pickup Hours", default="M-F: CALL FOR APPOINTMENT")
    pickup_instructions = fields.Text(string="Pickup Instructions")

    # ── Delivery Location Fields ────────────────────────────────────
    delivery_partner_id = fields.Many2one(
        "res.partner", string="Delivery Location",
        help="Consignee/delivery location for BOL"
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

    state = fields.Selection([
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
    ], default="draft", tracking=True)

    def write(self, vals):
        for rec in self:
            if rec.state in ["rate_confirmed", "scheduled", "dispatched", "picked_up", "delivered", "closed"]:
                if any(f in vals for f in ["origin_zip", "destination_zip"]):
                    raise UserError("Lane cannot be modified after rate confirmation.")
            if rec.state in ["dispatched", "picked_up", "delivered", "closed"]:
                blocked = set(vals.keys()) - {"bol_pickup_attached", "bol_delivery_attached"}
                if blocked:
                    raise UserError("Load locked after dispatch.")
        return super().write(vals)

    @api.depends("dispatched_at", "delivered_at")
    def _compute_cycle_time(self):
        for rec in self:
            if rec.dispatched_at and rec.delivered_at:
                delta = (rec.delivered_at - rec.dispatched_at).total_seconds() / 3600
                rec.cycle_time_hours = delta
            else:
                rec.cycle_time_hours = 0

    def action_confirm_ready(self, user_name):
        for rec in self:
            rec.ready_confirmed_by = user_name
            rec.ready_confirmed_at = fields.Datetime.now()
            rec._transition("ready_confirmed")

    def action_confirm_rate(self, rate):
        for rec in self:
            rec.rate_amount = rate
            rec.rate_confirmed_at = fields.Datetime.now()
            rec.rate_auto_reused = False
            rec._transition("rate_confirmed")
            rec._store_rate_memory()

    def action_schedule(self, pickup_dt, delivery_dt):
        for rec in self:
            rec.pickup_datetime = pickup_dt
            rec.delivery_datetime = delivery_dt
            rec._transition("scheduled")

    def action_dispatch(self):
        for rec in self:
            if rec.state not in ["scheduled", "rate_confirmed"]:
                raise UserError("Load must be scheduled and rate confirmed.")
            rec._transition("dispatched")

    def action_close(self):
        for rec in self:
            if not rec.bol_pickup_attached or not rec.bol_delivery_attached:
                raise UserError("BOL documents required.")
            rec._transition("closed")

    def _transition(self, new_state):
        for rec in self:
            correlation_id = new_correlation_id()
            old = rec.state
            vals = {"state": new_state, "entered_state_at": fields.Datetime.now()}
            if new_state == "dispatched":
                vals["dispatched_at"] = fields.Datetime.now()
            if new_state == "delivered":
                vals["delivered_at"] = fields.Datetime.now()
            rec.write(vals)
            # Log state transition (l9_trace integration disabled)
            _logger.info(
                "Load %s state transition: %s -> %s (correlation: %s)",
                rec.id, old, new_state, correlation_id
            )

    def _store_rate_memory(self):
        self.env["plasticos.rate.memory"].create({
            "carrier_id": self.carrier_id.id,
            "lane_key": self._lane_key(),
            "rate_amount": self.rate_amount,
            "rate_date": fields.Date.today(),
        })

    def _lane_key(self):
        so = self.sale_order_id
        return f"{so.partner_shipping_id.id}-{so.partner_invoice_id.id}"

    def _cron_escalation_check(self):
        from odoo.addons.plasticos_logistics.services.escalation_engine import check_escalations
        check_escalations(self.env)

    # ── Email Send Actions (Paperless) ──────────────────────────────

    def action_send_delivery_order(self):
        """Open email composer with Delivery Order attached."""
        self.ensure_one()
        template = self.env.ref(
            "plasticos_logistics_automation.mail_template_delivery_order",
            raise_if_not_found=False,
        )
        return self._open_mail_composer(template)

    def action_send_bol_pickup(self):
        """Open email composer with BOL Pickup attached."""
        self.ensure_one()
        template = self.env.ref(
            "plasticos_logistics_automation.mail_template_bol_pickup",
            raise_if_not_found=False,
        )
        return self._open_mail_composer(template)

    def action_send_bol_delivery(self):
        """Open email composer with BOL Delivery attached."""
        self.ensure_one()
        template = self.env.ref(
            "plasticos_logistics_automation.mail_template_bol_delivery",
            raise_if_not_found=False,
        )
        return self._open_mail_composer(template)

    def action_send_dispatch_packet(self):
        """Open email composer with full dispatch packet (all 3 docs)."""
        self.ensure_one()
        template = self.env.ref(
            "plasticos_logistics_automation.mail_template_dispatch_packet",
            raise_if_not_found=False,
        )
        return self._open_mail_composer(template)

    def _open_mail_composer(self, template):
        """Helper to open mail composer wizard with template."""
        ctx = {
            "default_model": "plasticos.load",
            "default_res_ids": self.ids,
            "default_template_id": template.id if template else False,
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

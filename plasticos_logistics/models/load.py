import hashlib
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models
from odoo.addons.plasticos_logistics.services.state_machine import VALID_TRANSITIONS, new_correlation_id
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import email_normalize

RES_PARTNER = "res.partner"
PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_LOAD = "plasticos.load"
OPERATIONS_MANAGER_GROUP = "plasticos_security_base.group_operations_manager"
_logger = logging.getLogger(__name__)

_FREIGHT_INTERNAL_WRITE = "plasticos_logistics_internal_freight_write"
_FREIGHT_INTERNAL_WRITE_TOKEN = object()
_FREIGHT_PROVENANCE_FIELDS = {
    "freight_context_fingerprint",
    "freight_context_version",
    "rate_confirmed_at",
    "rate_auto_reused",
    "rate_resolution_method",
    "sal_source_load_id",
    "sal_evaluated_at",
    "sal_decision",
    "sal_miss_reason",
    "sal_execution_failed",
    "sal_execution_failure_reason",
    "selected_freight_quote_id",
    "actual_freight_recorded_at",
}
_FREIGHT_RATE_INPUT_FIELDS = {"carrier_id", "rate_amount", "rate_currency_id"}
_FREIGHT_ACTUAL_INPUT_FIELDS = {"actual_freight_cost", "actual_freight_currency_id"}
_PROTECTED_PARENT_STATES = ("dispatched", "picked_up", "delivered", "closed")
_PARENT_CORRECTION = "plasticos_load_parent_correction"
_PARENT_CORRECTION_TOKEN = object()
_SCALE_TICKET_INTERNAL_WRITE = "plasticos_load_scale_ticket_status_write"
_SCALE_TICKET_INTERNAL_WRITE_TOKEN = object()
_SCALE_TICKET_STATUS_FIELDS = frozenset({"scale_ticket_reminder_sent", "scale_ticket_escalated"})
# Actual physical event clocks (BRS-EXP-10-R007). Only action_record_actual_event
# writes them; a state change or an import never does.
_ACTUAL_EVENT_INTERNAL_WRITE = "plasticos_load_actual_event_write"
_ACTUAL_EVENT_INTERNAL_WRITE_TOKEN = object()
_ACTUAL_EVENT_FIELDS = frozenset(
    {
        "actual_pickup_at",
        "actual_delivery_at",
        "pickup_evidence_attachment_id",
        "delivery_evidence_attachment_id",
    }
)
_ACTUAL_EVENT_KINDS = {
    "pickup": ("actual_pickup_at", "pickup_evidence_attachment_id", "actual_pickup_recorded"),
    "delivery": ("actual_delivery_at", "delivery_evidence_attachment_id", "actual_delivery_recorded"),
}


class _LindaProbeRollback(Exception):
    """Rolls back the probe run of a Linda actual event and carries its answer."""

    def __init__(self, result):
        super().__init__("probe")
        self.result = result


_ACTUAL_EVENT_EVIDENCE_MARKERS = (
    "needs the original document",
    "Attach the original to this load first",
    "must belong to the load's company",
)
_ACTUAL_EVENT_SEQUENCE_MARKERS = ("cannot be before actual pickup",)
ORIGINAL_NOT_VISIBLE = "The original document is not visible to you."


# Load fields Linda changes only through a gated command or an approval (C12 round 2, R1).
_LINDA_GATED_LOAD_FIELDS = frozenset({"state", "ready_confirmed_at", "ready_confirmed_by"}) | _ACTUAL_EVENT_FIELDS


def _refuse_linda_raw_write(env, field_names):
    """Linda's raw create/write of a gated load field is refused outside her gate or an approval."""
    from .linda_approval import linda_acting

    touched = _LINDA_GATED_LOAD_FIELDS.intersection(field_names)
    if touched and linda_acting(env):
        raise AccessError(
            "Linda changes a load's readiness, state or actual events only through its commands: "
            f"{', '.join(sorted(touched))}"
        )


def _actual_event_edge(message):
    """The Linda edge-case class of an actual-event refusal, or None for a plain refusal."""
    if any(marker in message for marker in _ACTUAL_EVENT_EVIDENCE_MARKERS):
        return "evidence_unverified"
    if any(marker in message for marker in _ACTUAL_EVENT_SEQUENCE_MARKERS):
        return "out_of_sequence"
    return None


# Operations that issue a NEW physical instruction to a carrier or site. Recording
# an event that already happened (picked_up, delivered, actual clocks) is not one.
PHYSICAL_RELEASE_OPERATIONS = ("schedule", "dispatch", "dispatch_packet", "carrier_document")
_RELEASE_STATES = {"scheduled": "schedule", "dispatched": "dispatch"}
_MILESTONE_LOAD_STATES = {
    "dispatched": ("dispatched", "picked_up", "delivered", "closed"),
    "in_transit": ("picked_up", "delivered", "closed"),
    "delivered": ("delivered", "closed"),
    "closed": ("closed",),
}
_TRANSACTION_JOIN_MILESTONE = {
    "dispatched": "dispatched",
    "in_progress": "dispatched",
    "in_transit": "in_transit",
    "delivered": "delivered",
    "invoiced": "delivered",
    "closed": "closed",
}
_DUPLICATE_CLEARED_FIELDS = (
    "transaction_id",
    "dispatched_at",
    "delivered_at",
    "entered_state_at",
    "pickup_datetime",
    "delivery_datetime",
    "bol_pickup_attached",
    "bol_delivery_attached",
    "dispatch_sent",
    "dispatch_acknowledged",
    "scale_ticket_reminder_sent",
    "scale_ticket_escalated",
    "actual_pickup_at",
    "actual_delivery_at",
    "pickup_evidence_attachment_id",
    "delivery_evidence_attachment_id",
)


class PlasticosLoad(models.Model):
    _name = "plasticos.load"
    _description = "Plasticos Logistics Load"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True, default=lambda self: self.env["ir.sequence"].next_by_code(PLASTICOS_LOAD) or "New"
    )
    sale_order_id = fields.Many2one("sale.order", ondelete="restrict")
    # Source-proven company (ADR-130). Taken from the sale order when there is one;
    # otherwise named explicitly for a buyerless movement. Never env.company.
    # Immutable once the load leaves Draft, has a parent, or carries evidence.
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="The load's own source company: its sale order's company, or the company named for a "
        "buyerless movement. It is never the user's current company by default.",
    )
    carrier_id = fields.Many2one(RES_PARTNER, string="Carrier", ondelete="restrict")
    rate_amount = fields.Float(string="Rate Amount")
    rate_confirmed_at = fields.Datetime()
    rate_auto_reused = fields.Boolean(default=False)
    rate_currency_id = fields.Many2one(
        "res.currency",
        string="Rate Currency",
        default=lambda self: self.env.company.currency_id,
        ondelete="restrict",
        help="Explicit currency for booked freight; required before a rate can qualify for SAL reuse.",
    )
    rate_resolution_method = fields.Selection(
        [("manual", "Manual"), ("sal", "Same As Last"), ("live_quote", "Live Quote")],
        string="Rate Resolution Method",
        readonly=True,
        tracking=True,
    )
    actual_freight_cost = fields.Monetary(currency_field="actual_freight_currency_id", tracking=True)
    actual_freight_currency_id = fields.Many2one(
        "res.currency", string="Actual Freight Currency", ondelete="restrict", tracking=True
    )
    actual_freight_recorded_at = fields.Datetime(readonly=True, tracking=True)
    freight_context_fingerprint = fields.Char(string="Freight Context Fingerprint", index=True, readonly=True)
    freight_context_version = fields.Char(string="Freight Context Version", readonly=True)
    sal_source_load_id = fields.Many2one(
        "plasticos.load",
        string="SAL Source Load",
        readonly=True,
        ondelete="restrict",
    )
    sal_evaluated_at = fields.Datetime(string="SAL Evaluated At", readonly=True)
    sal_decision = fields.Selection(
        [
            ("not_evaluated", "Not Evaluated"),
            ("hit", "Hit"),
            ("miss", "Miss"),
            ("not_eligible", "Not Eligible"),
        ],
        string="SAL Decision",
        default="not_evaluated",
        readonly=True,
    )
    sal_miss_reason = fields.Selection(
        [
            ("not_ready_confirmed", "Load Not Ready Confirmed"),
            ("missing_lane_identity", "Missing Lane or Repeat Stream"),
            ("already_rate_confirmed", "Rate Already Confirmed"),
            ("no_prior_movement", "No Prior Movement"),
            ("prior_movement_too_old", "Prior Movement Too Old"),
            ("prior_rate_missing", "Prior Rate or Currency Missing"),
            ("prior_carrier_inactive", "Prior Carrier Inactive"),
            ("prior_record_ambiguous", "Prior Record Ambiguous"),
        ],
        string="SAL Miss Reason",
        readonly=True,
    )
    sal_execution_failed = fields.Boolean(readonly=True, default=False)
    sal_execution_failure_reason = fields.Text(readonly=True)
    selected_freight_quote_id = fields.Many2one(
        "plasticos.freight.quote", string="Selected Freight Quote", readonly=True, ondelete="restrict"
    )
    freight_quote_request_ids = fields.One2many(
        "plasticos.freight.quote.request", "load_id", string="Freight Quote Requests"
    )
    freight_quote_request_count = fields.Integer(compute="_compute_freight_evidence_counts")
    freight_estimate_count = fields.Integer(compute="_compute_freight_evidence_counts")

    ready_confirmed_by = fields.Char()
    ready_confirmed_at = fields.Datetime()
    expected_ready_date = fields.Date(
        string="Expected Ready Date",
        tracking=True,
        help="The date the shipper reports the load will be staged. Distinct from the confirmation stamp (BRS-02-R005).",
    )
    ready_net_weight_lbs = fields.Float(
        string="Ready Net Weight (lb)",
        tracking=True,
        help="The full net weight the shipper says will be staged, in pounds. Zero means unknown.",
    )
    light_load_override_reason = fields.Text(
        string="Light Load Override Reason",
        tracking=True,
        help="Recorded when a person schedules or dispatches a load below the transaction minimum net weight.",
    )
    pickup_rebook_required = fields.Boolean(
        string="Pickup Rebook Required",
        tracking=True,
        help="Set when a changed delivery slot cancels the accepted pickup so it can be rebooked (BRS-03-R022).",
    )
    appointment_ids = fields.One2many("plasticos.load.appointment", "load_id", string="Appointments")

    pickup_datetime = fields.Datetime(string="Pickup Date/Time")
    delivery_datetime = fields.Datetime(string="Delivery Date/Time")

    bol_pickup_attached = fields.Boolean(default=False)
    bol_delivery_attached = fields.Boolean(default=False)

    # ── Actual physical event clocks (BRS-EXP-10-R007) ──────────────
    # Distinct from the scheduled pickup/delivery times and from the workflow
    # timestamps dispatched_at/delivered_at. Empty means unknown.
    actual_pickup_at = fields.Datetime(
        string="Actual Pickup",
        readonly=True,
        tracking=True,
        help="When the cargo was actually picked up, from attributed evidence. Empty means unknown.",
    )
    actual_delivery_at = fields.Datetime(
        string="Actual Delivery",
        readonly=True,
        tracking=True,
        help="When the cargo was actually delivered, from attributed evidence. Empty means unknown.",
    )
    pickup_evidence_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Pickup Evidence",
        readonly=True,
        ondelete="restrict",
        help="Original document attached to this load that attests the actual pickup.",
    )
    delivery_evidence_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Delivery Evidence",
        readonly=True,
        ondelete="restrict",
        help="Original document attached to this load that attests the actual delivery.",
    )

    entered_state_at = fields.Datetime(default=fields.Datetime.now, index=True)
    sla_breached = fields.Boolean(default=False, index=True)
    dispatched_at = fields.Datetime()
    delivered_at = fields.Datetime()
    cycle_time_hours = fields.Float(compute="_compute_cycle_time", store=True, index=True)

    # Stored parent. plasticos.transaction.load_ids is the inverse. One load, one parent.
    transaction_id = fields.Many2one(
        PLASTICOS_TRANSACTION,
        string="Transaction",
        index=True,
        ondelete="restrict",
        help="The single transaction this load belongs to. Empty when the load is not linked.",
    )

    # ── Delivery Term (editable with override tracking) ───────────────
    delivery_term = fields.Selection(
        [
            ("fcfs", "First Come First Served"),
            ("appointment", "Appointment Required"),
        ],
        string="Delivery Term",
        default=lambda self: self._get_default_delivery_term(),
        tracking=True,
        help="Defaults from transaction. Editable by logistics in rare cases (requires reason).",
    )
    delivery_term_override_reason = fields.Text(
        string="Override Reason",
        help="Required when delivery_term differs from transaction. Explain why the change was necessary.",
    )
    delivery_term_overridden = fields.Boolean(
        string="Delivery Term Overridden",
        compute="_compute_delivery_term_overridden",
        store=True,
        help="True if delivery_term differs from linked transaction.",
    )
    pickup_dock_rule = fields.Selection(
        [
            ("fcfs", "First Come First Served"),
            ("appointment", "Appointment Required"),
        ],
        string="Pickup Dock Rule",
        default=lambda self: self._get_default_pickup_dock_rule(),
        tracking=True,
        help="Defaults from the transaction pickup dock rule. An override requires a reason.",
    )
    pickup_dock_rule_override_reason = fields.Text(
        string="Pickup Override Reason",
        help="Required when pickup_dock_rule differs from the transaction. Explain why the change was necessary.",
    )
    pickup_dock_rule_overridden = fields.Boolean(
        string="Pickup Dock Rule Overridden",
        compute="_compute_pickup_dock_rule_overridden",
        store=True,
        help="True if pickup_dock_rule differs from the linked transaction.",
    )

    # ── Dispatch Tracking ─────────────────────────────────────────────
    dispatch_sent = fields.Datetime(
        string="Dispatch Sent",
        tracking=True,
        help="When dispatch notification was sent to carrier.",
    )
    dispatch_acknowledged = fields.Datetime(
        string="Dispatch Acknowledged",
        tracking=True,
        help="When carrier acknowledged the dispatch.",
    )
    dispatch_method = fields.Selection(
        [
            ("email", "Email"),
            ("sms", "SMS"),
            ("api", "API"),
            ("email_sms", "Email + SMS"),
        ],
        string="Dispatch Method",
        default="email",
        help="Method used to send dispatch notification.",
    )

    # ── Pickup Location Fields ──────────────────────────────────────
    pickup_partner_id = fields.Many2one(
        RES_PARTNER, string="Pickup Location", help="Shipper/pickup location for BOL", ondelete="restrict"
    )
    pickup_contact_name = fields.Char(string="Pickup Contact")
    pickup_contact_phone = fields.Char(string="Pickup Phone")
    pickup_contact_mobile = fields.Char(string="Pickup Mobile")
    pickup_reference = fields.Char(string="Pickup Reference/PO#")
    pickup_hours = fields.Char(
        string="Pickup Hours",
        default=lambda self: (
            self.env["ir.config_parameter"]
            .sudo()  # sudo: ir.config_parameter is settings-admin only
            .get_param("plasticos.load.default_pickup_hours", "M-F: 9:00 AM - 3:00 PM")
        ),
    )
    pickup_instructions = fields.Text(string="Pickup Instructions")

    # ── Delivery Location Fields ────────────────────────────────────
    delivery_partner_id = fields.Many2one(
        RES_PARTNER, string="Delivery Location", help="Consignee/delivery location for BOL", ondelete="restrict"
    )
    delivery_contact_name = fields.Char(string="Delivery Contact")
    delivery_contact_phone = fields.Char(string="Delivery Phone")
    delivery_contact_mobile = fields.Char(string="Delivery Mobile")
    delivery_reference = fields.Char(string="Delivery Reference/PO#")
    delivery_hours = fields.Char(
        string="Delivery Hours",
        default=lambda self: (
            self.env["ir.config_parameter"]
            .sudo()  # sudo: ir.config_parameter is settings-admin only
            .get_param("plasticos.load.default_delivery_hours", "M-F: 9:00 AM - 3:00 PM")
        ),
    )
    delivery_instructions = fields.Text(string="Delivery Instructions")

    # ── Carrier/Transport Fields ────────────────────────────────────
    carrier_contact_name = fields.Char(string="Carrier Contact")
    carrier_contact_phone = fields.Char(string="Carrier Phone")
    trailer_number = fields.Char(string="Trailer Number")
    seal_number = fields.Char(string="Seal Number")
    # Domestic road equipment for dispatch (BRS-EXP-07-R002). The type implies no
    # length, payload or VGM beyond what it names; the actual move states its own.
    road_equipment_type_id = fields.Many2one(
        "plasticos.road.equipment.type",
        string="Road Equipment",
        ondelete="restrict",
        tracking=True,
        help="Trailer the carrier brings for this move: 53 ft, 48 ft, flatbed or another type kept as data.",
    )
    road_equipment_requirements = fields.Text(
        string="Equipment Dimensions / Restrictions",
        help="Dimensions and restrictions of the actual move, e.g. a flatbed deck length. Not inferred from the type.",
    )

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

        Freight state and provenance are workflow-owned at creation exactly as in
        ``write()``: a caller cannot create a load already past Draft or carrying
        freight provenance, which would bypass operator checks, transitions and
        audit events.
        """
        internal_freight_write = self.env.context.get(_FREIGHT_INTERNAL_WRITE) is _FREIGHT_INTERNAL_WRITE_TOKEN
        for vals in vals_list:
            _refuse_linda_raw_write(self.env, vals)
        vals_list = [self._resolve_source_company(dict(vals), creating=True) for vals in vals_list]
        for vals in vals_list:
            self._fill_dock_rule_defaults(vals)
            self._fill_site_hours(vals)
        for vals in vals_list:
            actual = {name for name in _ACTUAL_EVENT_FIELDS.intersection(vals) if vals.get(name)}
            if actual:
                raise UserError(
                    "Actual pickup and delivery are recorded only from attributed evidence, "
                    f"through Record Actual Event: {', '.join(sorted(actual))}"
                )
        if not internal_freight_write:
            for vals in vals_list:
                if vals.get("state") not in (None, False, "draft"):
                    raise UserError(
                        "Loads are created in Draft; state may only change through the validated transition workflow."
                    )
                # Reject provenance by value, not key presence: an explicit
                # False/None (e.g. a cleared duplicate) carries no provenance.
                protected = {name for name in _FREIGHT_PROVENANCE_FIELDS.intersection(vals) if vals.get(name)}
                if protected:
                    raise UserError(
                        "Freight provenance may only be set through a validated freight command: "
                        f"{', '.join(sorted(protected))}"
                    )
        # The insert's foreign key takes a shared lock on the sale order.
        # Taking the exclusive lock first keeps two creates from deadlocking
        # when both later try to upgrade that shared lock.
        self._lock_rows("sale_order", [vals.get("sale_order_id") for vals in vals_list])
        self._lock_rows("plasticos_transaction", [vals.get("transaction_id") for vals in vals_list])
        records = super().create(vals_list)
        for rec in records:
            if rec.transaction_id:
                rec._require_join_milestone(rec.transaction_id)
        records._link_unique_sale_order_transaction()
        # A create that already names its parent does not go through write().
        # Auto-linked loads bump the parent from that write.
        direct_parent_ids = [vals.get("transaction_id") for vals in vals_list if vals.get("transaction_id")]
        if direct_parent_ids:
            records._touch_membership_epoch(direct_parent_ids)
        return records

    # ── Source company (ADR-130, BRS-EXP-08-R008) ─────────────────────

    def _check_company_allowed(self, company):
        """An explicitly named company must be one the acting user may work in."""
        if self.env.su or not company:
            return
        if company not in self.env.user.company_ids:
            raise AccessError(f"You cannot create or move a load in company {company.display_name}.")

    def _resolve_source_company(self, vals, creating=False):
        """Derive the load company from its sale order, or check the named one.

        The sale order is the source when there is one, and a different named
        company is refused. A buyerless movement names its company explicitly;
        the acting user's current company is never taken as the source.
        """
        sale_order_id = vals.get("sale_order_id")
        named_company_id = vals.get("company_id")
        if sale_order_id:
            source_company = self.env["sale.order"].browse(sale_order_id).company_id
            if named_company_id and source_company and named_company_id != source_company.id:
                raise ValidationError("A load's company must be the company of its sale order.")
            if source_company:
                vals["company_id"] = source_company.id
        elif named_company_id:
            self._check_company_allowed(self.env["res.company"].browse(named_company_id))
        elif creating and not self.env.su:
            raise UserError(
                "A load needs its source company: choose its sale order, or name the company for a buyerless movement."
            )
        return vals

    def _company_is_locked(self):
        """The company is accepted once the load leaves Draft, has a parent, or carries evidence."""
        self.ensure_one()
        return bool(
            self.state != "draft"
            or self.transaction_id
            or self._has_freight_provenance()
            or self.actual_pickup_at
            or self.actual_delivery_at
        )

    def _guard_company_change(self, new_company_id):
        for rec in self:
            if rec.company_id.id == (new_company_id or False):
                continue
            # A load whose company is cleared would vanish behind the global
            # company rule for every user. Only the superuser may clear it.
            if rec.company_id and not new_company_id and not self.env.su:
                raise ValidationError(
                    f"Load {rec.name} keeps its company. Choose another company in Draft instead of clearing it."
                )
            if rec.company_id and rec._company_is_locked():
                raise ValidationError(f"Load {rec.name} has an accepted company. It cannot move to another company.")

    @api.onchange("sale_order_id")
    def _onchange_sale_order_company(self):
        for rec in self:
            if rec.sale_order_id and rec.sale_order_id.company_id:
                rec.company_id = rec.sale_order_id.company_id

    @api.constrains("company_id", "sale_order_id")
    def _check_company_matches_sale_order(self):
        for rec in self:
            source_company = rec.sale_order_id.company_id
            if source_company and rec.company_id != source_company:
                raise ValidationError(f"Load {rec.name}: its company must be the company of its sale order.")

    def _touch_membership_epoch(self, parent_ids=None):
        """Bump parent row versions when load membership changes.

        Odoo cursors use REPEATABLE READ. SELECT FOR UPDATE does not show a
        load committed after this snapshot, and it raises serialization_failure
        only when the locked row was actually updated. A primary-key update
        would cascade through foreign keys, so the bump writes write_date.
        """
        ids = {
            row_id
            for row_id in set(parent_ids or ()) | set(self.mapped("transaction_id").ids)
            if isinstance(row_id, int)
        }
        if not ids:
            return
        ordered_ids = tuple(sorted(ids))
        self._lock_rows("plasticos_transaction", ordered_ids)
        self.env.cr.execute(
            "UPDATE plasticos_transaction SET write_date = (clock_timestamp() AT TIME ZONE 'UTC') WHERE id IN %s",
            [ordered_ids],
        )
        self.env["plasticos.transaction"].browse(ordered_ids).invalidate_recordset(["write_date"])

    def _lock_rows(self, table, ids):
        row_ids = tuple(sorted({row_id for row_id in ids if row_id}))
        if not row_ids:
            return
        if table == "sale_order":
            query = "SELECT id FROM sale_order WHERE id IN %s ORDER BY id FOR UPDATE"
        elif table == "plasticos_transaction":
            query = "SELECT id FROM plasticos_transaction WHERE id IN %s ORDER BY id FOR UPDATE"
        elif table == "plasticos_load":
            query = "SELECT id FROM plasticos_load WHERE id IN %s ORDER BY id FOR UPDATE"
        else:
            raise ValidationError("Cannot lock an unexpected table while assigning a load.")
        self.env.cr.execute(query, [row_ids])

    def _eligible_transactions_for_sale_orders(self, sale_orders):
        """Eligible parents for these sale orders, grouped by sale order id."""
        grouped = {}
        eligible = self.env[PLASTICOS_TRANSACTION]
        if not sale_orders:
            return grouped, eligible
        eligible = self.env[PLASTICOS_TRANSACTION].search(
            [
                ("sale_order_id", "in", sale_orders.ids),
                ("supplier_id", "!=", False),
                ("buyer_id", "!=", False),
            ]
        )
        empty = self.env[PLASTICOS_TRANSACTION]
        grouped = {sale_order.id: empty for sale_order in sale_orders}
        for transaction in eligible:
            grouped[transaction.sale_order_id.id] |= transaction
        return grouped, eligible

    def _eligible_transactions(self, sale_order):
        grouped, _eligible = self._eligible_transactions_for_sale_orders(sale_order)
        return grouped.get(sale_order.id, self.env[PLASTICOS_TRANSACTION])

    def _write_transaction_parent(self, transaction_id):
        """Assign one parent to every load in this recordset that does not already have it."""
        pending = self.filtered(lambda load: load.transaction_id.id != transaction_id)
        if pending:
            pending.write({"transaction_id": transaction_id})

    def _write_parent_assignments(self, assignments):
        """Write each parent once for the loads that passed that parent's checks."""
        grouped = {}
        for load, transaction_id in assignments:
            grouped.setdefault(transaction_id, self.browse())
            grouped[transaction_id] |= load
        for transaction_id, loads in grouped.items():
            loads._write_transaction_parent(transaction_id)

    def _parent_route(self, transaction):
        """``sale`` when either side names a sale order, else ``purchase`` (buyerless)."""
        self.ensure_one()
        return "sale" if (self.sale_order_id or transaction.sale_order_id) else "purchase"

    def _parent_identity_error(self, transaction):
        """Refuse a new parent whose commercial identity is missing or different.

        Two routes (BRS-EXP-08-R008, BRS-EXP-10-R008):

        * sale-backed: the load and its transaction share one sale order and its
          company, and the transaction names a real supplier and buyer;
        * purchase-backed (buyerless): neither side has a sale order; the
          transaction has its supplier purchase orders, all in the load's proven
          company, and its supplier. No buyer is required or invented.

        Every purchase order on the transaction must belong to the load's company.
        """
        self.ensure_one()
        load_company = self.company_id
        purchase_companies = transaction.purchase_order_ids.company_id if transaction.purchase_order_ids else None
        if self._parent_route(transaction) == "sale":
            if not self.sale_order_id or not transaction.sale_order_id:
                return "A load and its transaction both need a sale order."
            if self.sale_order_id != transaction.sale_order_id:
                return "A load must use the same sale order as its transaction."
            transaction_company = transaction.sale_order_id.company_id
            if bool(load_company) != bool(transaction_company) or (
                load_company and transaction_company and load_company != transaction_company
            ):
                return "A load cannot join a transaction across companies or with an unknown company."
            if purchase_companies and purchase_companies != load_company:
                return "A load cannot join a transaction whose purchase orders belong to another company."
            if not transaction.supplier_id or not transaction.buyer_id:
                return "Cannot link a load until the transaction has both a supplier and a buyer."
            return None
        if not load_company:
            return "A buyerless load needs its proven company before it can join a transaction."
        if not transaction.purchase_order_ids:
            return "A load without a sale order can join only a transaction backed by its supplier purchase order."
        if purchase_companies != load_company:
            return "A load cannot join a transaction across companies or with an unknown company."
        if not transaction.supplier_id:
            return "Cannot link a buyerless load until the transaction has its supplier."
        return None

    def _join_milestone_error(self, transaction):
        self.ensure_one()
        milestone = _TRANSACTION_JOIN_MILESTONE.get(transaction.state)
        if milestone and self.state not in _MILESTONE_LOAD_STATES[milestone]:
            return (
                f"Load {self.name} cannot join transaction {transaction.name} "
                f"after that transaction has reached {transaction.state}."
            )
        return None

    def _require_parent_identity(self, transaction):
        error = self._parent_identity_error(transaction)
        if error:
            raise ValidationError(error)

    def _require_join_milestone(self, transaction):
        error = self._join_milestone_error(transaction)
        if error:
            raise ValidationError(error)

    @api.model
    def _loads_blocking_milestone(self, loads, milestone):
        allowed = _MILESTONE_LOAD_STATES[milestone]
        return loads.filtered(lambda load: load.state not in allowed)

    def copy(self, default=None):
        """A duplicate is a new draft. It does not inherit the source load's parent."""
        copied = self.with_context(plasticos_skip_load_parent_link=True)
        return super(PlasticosLoad, copied).copy(default=default)

    def _link_unique_sale_order_transaction(self):
        """Link a new load only when its sale order has one eligible transaction.

        Zero matches stay unlinked. Two or more eligible transactions are refused
        so the create rolls back instead of picking a sale order's first row.
        Sale orders are locked, eligible transactions are read again under those
        locks, and only then are these loads locked and refreshed.
        Only loads in this recordset are candidates. Another unlinked load on a
        different sale order is left untouched.
        """
        if self.env.context.get("plasticos_skip_load_parent_link"):
            return
        pending = self.filtered(lambda rec: not rec.transaction_id and rec.sale_order_id)
        if not pending:
            return
        sale_orders = pending.sale_order_id
        self._lock_rows("sale_order", sale_orders.ids)
        _grouped, eligible = self._eligible_transactions_for_sale_orders(sale_orders)
        self._lock_rows("plasticos_transaction", eligible.ids)
        grouped, _eligible = self._eligible_transactions_for_sale_orders(sale_orders)
        self._lock_rows("plasticos_load", pending.ids)
        pending.invalidate_recordset(["transaction_id", "sale_order_id", "company_id"])
        assignments = []
        for rec in pending:
            if rec.transaction_id or not rec.sale_order_id:
                continue
            candidates = grouped.get(rec.sale_order_id.id, self.env[PLASTICOS_TRANSACTION])
            if len(candidates) > 1:
                raise ValidationError(
                    f"Sale order {rec.sale_order_id.display_name} matches {len(candidates)} transactions "
                    "with supplier and buyer. Assign the transaction explicitly."
                )
            if len(candidates) == 1:
                rec._require_parent_identity(candidates)
                rec._require_join_milestone(candidates)
                assignments.append((rec, candidates.id))
        self._write_parent_assignments(assignments)

    @api.model
    def _reconcile_unlinked_for_transactions(self, transactions):
        """Link unlinked loads when a sale order later has exactly one eligible transaction.

        More than one eligible transaction skips that sale order. An identity or
        milestone failure leaves that load unlinked. A protected load is skipped
        before the parent write.
        """
        qualified = transactions.filtered(lambda tx: tx.sale_order_id and tx.supplier_id and tx.buyer_id)
        if not qualified:
            return
        sale_orders = qualified.sale_order_id
        self._lock_rows("sale_order", sale_orders.ids)
        _grouped, eligible = self._eligible_transactions_for_sale_orders(sale_orders)
        self._lock_rows("plasticos_transaction", eligible.ids)
        grouped, _eligible = self._eligible_transactions_for_sale_orders(sale_orders)
        linkable = self.env[PLASTICOS_TRANSACTION]
        for tx in qualified:
            candidates = grouped.get(tx.sale_order_id.id, self.env[PLASTICOS_TRANSACTION])
            if len(candidates) == 1 and candidates == tx:
                linkable |= tx
        if not linkable:
            return
        domain = [("sale_order_id", "in", linkable.sale_order_id.ids), ("transaction_id", "=", False)]
        loads = self.search(domain)
        self._lock_rows("plasticos_load", loads.ids)
        loads.invalidate_recordset(["transaction_id", "sale_order_id", "company_id"])
        loads = self.search(domain)
        protected = loads._protected_parent_loads()
        parent_by_sale = {tx.sale_order_id.id: tx for tx in linkable}
        assignments = []
        for load in loads:
            if load in protected:
                continue
            tx = parent_by_sale.get(load.sale_order_id.id)
            if not tx or load._parent_identity_error(tx) or load._join_milestone_error(tx):
                continue
            assignments.append((load, tx.id))
        self._write_parent_assignments(assignments)

    def _has_freight_provenance(self):
        self.ensure_one()
        if self.rate_confirmed_at or self.actual_freight_recorded_at or self.selected_freight_quote_id:
            return True
        if self.freight_context_fingerprint or self.sal_evaluated_at or self.sal_source_load_id:
            return True
        if self.rate_auto_reused or self.sal_execution_failed or self.sal_miss_reason:
            return True
        return self.sal_decision not in (False, "not_evaluated")

    def _protected_parent_loads(self):
        """Loads whose parent cannot move: dispatched, evidenced, quoted, or on a dispatch."""
        protected = self.browse()
        if not self:
            return protected
        for rec in self:
            if rec.state in _PROTECTED_PARENT_STATES or rec._has_freight_provenance() or rec.freight_quote_request_ids:
                protected |= rec
        remaining = self - protected
        if remaining and "plasticos.dispatch" in self.env:
            dispatches = self.env["plasticos.dispatch"].search([("load_id", "in", remaining.ids)])
            protected |= dispatches.load_id
        return protected

    def _parent_link_is_protected(self):
        """Dispatched loads and loads that already carry evidence cannot be reparented."""
        self.ensure_one()
        return self in self._protected_parent_loads()

    def _guard_transaction_parent(self, new_tx_id):
        """Keep a load on its current transaction. A failed write leaves that link.

        An ordinary write cannot clear or move a parent, including a two-step
        clear followed by a new assignment. A draft correction goes through
        ``action_correct_draft_parent`` and still cannot detach protected evidence.
        """
        new_tx_id = new_tx_id or False
        if not self:
            return
        authorized = self.env.context.get(_PARENT_CORRECTION) is _PARENT_CORRECTION_TOKEN
        sale_ids = set(self.mapped("sale_order_id").ids)
        transaction_ids = set(self.mapped("transaction_id").ids)
        if new_tx_id:
            transaction_ids.add(new_tx_id)
            target = self.env[PLASTICOS_TRANSACTION].browse(new_tx_id).exists()
            if target.sale_order_id:
                sale_ids.add(target.sale_order_id.id)
        self._lock_rows("sale_order", sale_ids)
        self._lock_rows("plasticos_transaction", transaction_ids)
        self._lock_rows("plasticos_load", self.ids)
        self.invalidate_recordset(["transaction_id", "sale_order_id", "company_id"])
        protected = self.filtered("transaction_id")._protected_parent_loads()
        for rec in self:
            current_id = rec.transaction_id.id
            if current_id == new_tx_id:
                continue
            if current_id and rec in protected:
                raise ValidationError(
                    f"Load {rec.name} is dispatched or carries freight, dispatch, or accepted evidence. "
                    "Its transaction link stays unchanged."
                )
            if current_id and not authorized:
                raise ValidationError(
                    f"Load {rec.name} stays on its transaction. Correct a draft link with an attributable reason."
                )
            if new_tx_id:
                target = self.env[PLASTICOS_TRANSACTION].browse(new_tx_id).exists()
                if not target:
                    raise ValidationError("Cannot link a load to a missing transaction.")
                rec._require_parent_identity(target)
                rec._require_join_milestone(target)

    def action_correct_draft_parent(self, transaction, reason):
        """Move or clear a draft parent in one attributable write."""
        self.ensure_one()
        explanation = (reason or "").strip()
        if not explanation:
            raise UserError("A reason is required to correct a draft load's transaction.")
        if self._parent_link_is_protected():
            raise ValidationError(
                f"Load {self.name} is dispatched or carries freight, dispatch, or accepted evidence. "
                "Its transaction link stays unchanged."
            )
        new_id = transaction.id if transaction else False
        self.with_context(**{_PARENT_CORRECTION: _PARENT_CORRECTION_TOKEN}).write({"transaction_id": new_id})
        self.message_post(body=f"Draft transaction link corrected. {explanation}")

    def _write_scale_ticket_status(self, values):
        """Record reminder or escalation state without opening the load to other edits."""
        unknown = set(values) - _SCALE_TICKET_STATUS_FIELDS
        if unknown:
            raise UserError(f"Scale-ticket status cannot write {', '.join(sorted(unknown))}.")
        return self.with_context(**{_SCALE_TICKET_INTERNAL_WRITE: _SCALE_TICKET_INTERNAL_WRITE_TOKEN}).write(values)

    @api.constrains("transaction_id", "sale_order_id")
    def _check_transaction_parent(self):
        for rec in self:
            if rec.transaction_id:
                rec._require_parent_identity(rec.transaction_id)

    def copy_data(self, default=None):
        """A duplicated load starts in Draft without a parent, dates, or evidence."""
        default = dict(default or {})
        default.setdefault("state", "draft")
        for name in _FREIGHT_PROVENANCE_FIELDS:
            default.setdefault(name, False)
        for name in _DUPLICATE_CLEARED_FIELDS:
            if name in self._fields:
                default.setdefault(name, False)
        return super().copy_data(default=default)

    def unlink(self):
        # Delete and milestone reads share sale order, then transaction, then load.
        parent_ids = self.mapped("transaction_id").ids
        self._lock_rows("sale_order", self.mapped("sale_order_id").ids)
        self._lock_rows("plasticos_transaction", parent_ids)
        self._lock_rows("plasticos_load", self.ids)
        self.invalidate_recordset(["transaction_id", "sale_order_id", "state"])
        parent_ids = self.mapped("transaction_id").ids
        protected = self._protected_parent_loads()
        for rec in self:
            if rec in protected:
                raise UserError(
                    f"Load {rec.name} is dispatched or carries freight, dispatch, or accepted evidence "
                    "and cannot be deleted."
                )
        result = super().unlink()
        self.env["plasticos.load"]._touch_membership_epoch(parent_ids)
        return result

    def _compute_freight_evidence_counts(self):
        request_counts = {}
        estimate_counts = {}
        if self.ids:
            request_rows = self.env["plasticos.freight.quote.request"]._read_group(
                [("load_id", "in", self.ids)],
                ["load_id"],
                ["__count"],
            )
            request_counts = {load.id: count for load, count in request_rows if load}
            estimate_rows = self.env["plasticos.freight.estimate"]._read_group(
                [("source_model", "=", PLASTICOS_LOAD), ("source_record_id", "in", self.ids)],
                ["source_record_id"],
                ["__count"],
            )
            estimate_counts = {source_id: count for source_id, count in estimate_rows}
        for rec in self:
            rec.freight_quote_request_count = request_counts.get(rec.id, 0)
            rec.freight_estimate_count = estimate_counts.get(rec.id, 0)

    def _require_freight_operator(self):
        """Require the Logistics business role for freight command boundaries."""
        if self.env.uid == SUPERUSER_ID:
            return
        if not self.env.user.has_group("plasticos_security_base.group_logistics"):
            raise AccessError("Only Logistics users may execute freight commands.")
        self.check_access_rights("write")
        self.check_access_rule("write")

    def _freight_write(self, values):
        """Use the narrow internal capability after a canonical freight command validates."""
        return self.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(values)

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
        vals = dict(vals)
        _refuse_linda_raw_write(self.env, vals)
        if "sale_order_id" in vals or "company_id" in vals:
            if vals.get("sale_order_id") or vals.get("company_id"):
                self._resolve_source_company(vals)
            if "company_id" in vals:
                self._guard_company_change(vals.get("company_id"))
        freight_fields = set(vals)
        internal_freight_write = self.env.context.get(_FREIGHT_INTERNAL_WRITE) is _FREIGHT_INTERNAL_WRITE_TOKEN
        internal_scale_ticket_write = (
            self.env.context.get(_SCALE_TICKET_INTERNAL_WRITE) is _SCALE_TICKET_INTERNAL_WRITE_TOKEN
        )
        internal_actual_event_write = (
            self.env.context.get(_ACTUAL_EVENT_INTERNAL_WRITE) is _ACTUAL_EVENT_INTERNAL_WRITE_TOKEN
        )
        if _ACTUAL_EVENT_FIELDS.intersection(freight_fields) and not internal_actual_event_write:
            raise UserError(
                "Actual pickup and delivery are recorded only from attributed evidence, through Record Actual Event."
            )
        if not internal_freight_write:
            if "state" in freight_fields:
                raise UserError("Load state may only change through the validated transition workflow.")
            protected = _FREIGHT_PROVENANCE_FIELDS.intersection(freight_fields)
            if protected:
                raise UserError(
                    "Freight provenance may only change through a validated freight command: "
                    f"{', '.join(sorted(protected))}"
                )
            if _FREIGHT_RATE_INPUT_FIELDS.intersection(freight_fields) or _FREIGHT_ACTUAL_INPUT_FIELDS.intersection(
                freight_fields
            ):
                self._require_freight_operator()
            for rec in self:
                if _FREIGHT_RATE_INPUT_FIELDS.intersection(freight_fields) and rec.rate_confirmed_at:
                    raise UserError(
                        "Confirmed freight rate inputs are immutable; create a new freight resolution instead."
                    )
                if _FREIGHT_ACTUAL_INPUT_FIELDS.intersection(freight_fields) and rec.actual_freight_recorded_at:
                    raise UserError(
                        "Recorded actual freight is immutable; use the attributed calibration correction workflow."
                    )

        old_parent_ids = ()
        if "transaction_id" in vals:
            old_parent_ids = self.mapped("transaction_id").ids
            self._guard_transaction_parent(vals.get("transaction_id"))

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
                    # Dispatch tracking fields (added for logistics enhancement)
                    "dispatch_sent",
                    "dispatch_acknowledged",
                    "dispatch_method",
                    # Delivery term override (rare but allowed)
                    "delivery_term",
                    "delivery_term_override_reason",
                    "delivery_term_overridden",
                    "pickup_dock_rule",
                    "pickup_dock_rule_override_reason",
                    "pickup_dock_rule_overridden",
                }
                if internal_freight_write:
                    allowed.update(_FREIGHT_ACTUAL_INPUT_FIELDS | {"actual_freight_recorded_at"})
                if internal_scale_ticket_write:
                    allowed.update(_SCALE_TICKET_STATUS_FIELDS)
                if internal_actual_event_write:
                    allowed.update(_ACTUAL_EVENT_FIELDS)
                blocked = set(vals.keys()) - allowed
                if blocked:
                    raise UserError(f"Load locked after dispatch. Cannot modify: {', '.join(sorted(blocked))}")

        res = super().write(vals)
        if "transaction_id" in vals:
            self._touch_membership_epoch(old_parent_ids)

        if "state" in vals and vals["state"] == "closed":
            for rec in self:
                tx = rec.transaction_id
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

    def _get_default_delivery_term(self):
        """Get delivery term from linked transaction if available."""
        tx_id = self.env.context.get("default_transaction_id")
        if tx_id:
            tx = self.env[PLASTICOS_TRANSACTION].browse(tx_id)
            if tx.delivery_term:
                return tx.delivery_term
        return "appointment"

    def _get_default_pickup_dock_rule(self):
        """Pickup dock rule from the linked transaction, else Appointment."""
        tx_id = self.env.context.get("default_transaction_id")
        if tx_id:
            tx = self.env[PLASTICOS_TRANSACTION].browse(tx_id)
            if tx.pickup_dock_rule:
                return tx.pickup_dock_rule
        return "appointment"

    def _fill_dock_rule_defaults(self, vals):
        """Copy both sides from a transaction named on create. Explicit values stay."""
        tx_id = vals.get("transaction_id")
        if not tx_id:
            return
        tx = self.env[PLASTICOS_TRANSACTION].browse(tx_id)
        if "delivery_term" not in vals and tx.delivery_term:
            vals["delivery_term"] = tx.delivery_term
        if "pickup_dock_rule" not in vals and tx.pickup_dock_rule:
            vals["pickup_dock_rule"] = tx.pickup_dock_rule

    def _partner_shipping_hours(self, partner_id):
        if not partner_id:
            return ""
        partner = self.env[RES_PARTNER].browse(partner_id)
        if "shipping_hours" not in partner._fields:
            return ""
        return partner.shipping_hours or ""

    def _fill_site_hours(self, vals):
        """Default pickup and delivery hours from the site, then the existing config text."""
        from ..schedule_window import hours_default

        params = self.env["ir.config_parameter"].sudo()  # sudo: ir.config_parameter is settings-admin only
        if "pickup_hours" not in vals:
            fallback = params.get_param("plasticos.load.default_pickup_hours", "M-F: 9:00 AM - 3:00 PM")
            vals["pickup_hours"] = hours_default(self._partner_shipping_hours(vals.get("pickup_partner_id")), fallback)
        if "delivery_hours" not in vals:
            fallback = params.get_param("plasticos.load.default_delivery_hours", "M-F: 9:00 AM - 3:00 PM")
            vals["delivery_hours"] = hours_default(
                self._partner_shipping_hours(vals.get("delivery_partner_id")), fallback
            )

    @api.onchange("pickup_partner_id")
    def _onchange_pickup_hours_from_site(self):
        for rec in self:
            site = rec._partner_shipping_hours(rec.pickup_partner_id.id)
            if site and not rec.pickup_hours:
                rec.pickup_hours = site

    @api.onchange("delivery_partner_id")
    def _onchange_delivery_hours_from_site(self):
        for rec in self:
            site = rec._partner_shipping_hours(rec.delivery_partner_id.id)
            if site and not rec.delivery_hours:
                rec.delivery_hours = site

    @api.depends("delivery_term", "transaction_id.delivery_term")
    def _compute_delivery_term_overridden(self):
        """Check if delivery_term differs from the linked transaction."""
        for rec in self:
            tx = rec.transaction_id
            if tx and tx.delivery_term:
                rec.delivery_term_overridden = rec.delivery_term != tx.delivery_term
            else:
                rec.delivery_term_overridden = False

    @api.depends("pickup_dock_rule", "transaction_id.pickup_dock_rule")
    def _compute_pickup_dock_rule_overridden(self):
        """True when the load pickup rule differs from the linked transaction."""
        for rec in self:
            tx = rec.transaction_id
            if tx and tx.pickup_dock_rule:
                rec.pickup_dock_rule_overridden = rec.pickup_dock_rule != tx.pickup_dock_rule
            else:
                rec.pickup_dock_rule_overridden = False

    @api.constrains(
        "delivery_term",
        "delivery_term_override_reason",
        "pickup_dock_rule",
        "pickup_dock_rule_override_reason",
    )
    def _check_override_reason_required(self):
        """Require a reason when either dock rule differs from the transaction."""
        for rec in self:
            if rec.delivery_term_overridden and not rec.delivery_term_override_reason:
                raise ValidationError(
                    "Override reason is required when changing delivery term from transaction default."
                )
            if rec.pickup_dock_rule_overridden and not rec.pickup_dock_rule_override_reason:
                raise ValidationError(
                    "Override reason is required when changing the pickup dock rule from the transaction default."
                )

    def action_confirm_ready(self):
        """Confirm load is ready for pickup. Captures authenticated user.

        Linda's confirmation is held for an Operations Manager (C12-SCOPE-3 (1)) and
        returns ``{status: pending, approval_id, reason}``; a person's applies at once.
        """
        from .linda_approval import linda_acting, linda_stop

        stop = linda_stop(self.env)
        if stop:
            return stop
        if linda_acting(self.env):
            return self._linda_confirm_ready_gate()
        for rec in self:
            rec._require_freight_operator()
            rec.ready_confirmed_by = self.env.user.name
            rec.ready_confirmed_at = fields.Datetime.now()
            rec._transition("ready_confirmed")

    def _linda_confirm_ready_gate(self):
        from .linda_approval import hold_for_approval, prior_refusal

        held = []
        for rec in self:
            rec.check_access("read")
            if not rec.company_id:
                held.append(
                    {"status": "blocked", "record_id": rec.id, "reason": f"Load {rec.name} needs its proven company"}
                )
                continue
            if rec.state == "ready_confirmed":
                held.append({"status": "already_applied", "record_id": rec.id})
                continue
            subject_key = f"load:{rec.id}"
            retry = prior_refusal(self.env, "confirm_ready", subject_key, rec.company_id)
            held.append(
                hold_for_approval(
                    self.env,
                    "confirm_ready",
                    "refusal_retry" if retry else "acceptance",
                    f"Linda confirms load {rec.name} ready for pickup",
                    {"load_id": rec.id},
                    f"confirm_ready:{rec.id}",
                    rec.company_id,
                    rec,
                    subject_key=subject_key,
                )
            )
        return held[0] if len(held) == 1 else held

    def _lock_freight_advisories(self, prefix):
        """Take this command's advisory locks in load-id order."""
        for rec in self.sorted(key=lambda load: load.id):
            self.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                [f"plasticos_logistics.{prefix}:{rec.id}"],
            )

    def action_create_freight_quote_request(self):
        """Create one manual-only RFQ episode after a current SAL miss.

        This persists a recipient/evidence workflow but deliberately performs no
        outbound delivery until an approved channel and RFQ terms exist.
        """
        from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_events
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context,
        )

        request_model = self.env["plasticos.freight.quote.request"]
        prepared = []
        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            if rec.state != "ready_confirmed" or rec.sal_decision not in ("miss", "not_eligible"):
                raise UserError(
                    "A current SAL miss or not-eligible decision is required before creating an RFQ episode."
                )
            context = build_freight_context(rec)
            if not context:
                raise UserError("A complete freight context is required before creating an RFQ episode.")
            if rec.freight_context_fingerprint != context.fingerprint:
                raise UserError("Freight context changed. Re-run freight resolution before creating an RFQ episode.")
            prepared.append((rec, correlation_id, context))
        self.browse([rec.id for rec, _correlation_id, _context in prepared])._lock_freight_advisories("rfq")
        work = []
        for rec, correlation_id, context in prepared:
            key = hashlib.sha256(f"rfq:{rec.id}:{context.fingerprint}".encode()).hexdigest()
            work.append((rec, correlation_id, context, key))
        existing_keys = set()
        if work:
            existing_keys = set(
                request_model.search([("idempotency_key", "in", [item[3] for item in work])]).mapped("idempotency_key")
            )
        vals_list = []
        pending = []
        for rec, correlation_id, context, key in work:
            if key in existing_keys:
                continue
            company = rec.sale_order_id.company_id if rec.sale_order_id else False
            if not company or not rec.transaction_id:
                raise UserError("Load company and transaction are required before creating an RFQ episode.")
            vals_list.append(
                {
                    "company_id": company.id,
                    "context_fingerprint": context.fingerprint,
                    "fingerprint_version": FREIGHT_CONTEXT_VERSION,
                    "idempotency_key": key,
                    "load_id": rec.id,
                    "origin_partner_id": rec.pickup_partner_id.id,
                    "destination_partner_id": rec.delivery_partner_id.id,
                    "sal_decision": rec.sal_decision,
                    "sal_miss_reason": rec.sal_miss_reason or "not_eligible",
                    "transaction_id": rec.transaction_id.id,
                }
            )
            pending.append((rec, correlation_id))
        if not vals_list:
            return True
        created = request_model.create(vals_list)
        by_load = {request.load_id.id: request for request in created}
        events = []
        for rec, correlation_id in pending:
            request = by_load[rec.id]
            rec.message_post(
                body=f"Manual-only freight RFQ episode {request.name} created; no outbound carrier send was performed."
            )
            events.append(
                {
                    "event_type": "rfq_request_created",
                    "outcome_code": "manual_only",
                    "load": rec,
                    "facts": {"request_id": request.id},
                    "unknowns": ["recipient_policy_unapproved", "outbound_delivery_unavailable"],
                    "correlation_id": correlation_id,
                }
            )
        record_freight_events(self.env, events)
        return True

    def action_request_freight_estimate(self):
        """Persist a nonbinding local Haversine-curve estimate from canonical evidence."""
        from odoo.addons.plasticos_logistics.models.freight_governance import (
            create_freight_evidence_rows,
            record_freight_events,
        )
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context,
        )
        from odoo.addons.plasticos_logistics.services.freight_estimation import (
            ESTIMATOR_MODEL_VERSION,
            ESTIMATOR_POLICY_VERSION,
            estimate_haversine_curve,
        )
        from odoo.addons.plasticos_logistics.services.freight_geometry import FreightCoordinateError
        from odoo.addons.plasticos_logistics.services.freight_history import (
            bounded_evidence_payload,
            local_estimation_evidence,
            recent_comparable_executed_evidence,
            recent_executed_lane_evidence,
        )

        for rec in self:
            rec._require_freight_operator()
        self._lock_freight_advisories("estimate")
        self.invalidate_recordset()
        prepared = []
        for rec in self:
            correlation_id = new_correlation_id()
            context = build_freight_context(rec)
            if not context:
                raise UserError("A complete freight context is required before an estimate can be requested.")
            currency = rec.rate_currency_id
            if not currency:
                raise UserError("An explicit freight currency is required before an estimate can be requested.")
            if not (
                getattr(rec, "company_id", False) or (rec.sale_order_id.company_id if rec.sale_order_id else False)
            ):
                raise UserError("Load company is required before an estimate can be recorded.")
            exact_history = recent_executed_lane_evidence(rec.env, rec)
            exact_ids = exact_history.ids
            comparable_history = recent_comparable_executed_evidence(rec.env, rec).filtered(
                lambda candidate, exact_ids=exact_ids: candidate.id not in exact_ids
            )
            history_records = exact_history + comparable_history
            try:
                proposal = estimate_haversine_curve(
                    origin_latitude=rec.pickup_partner_id.partner_latitude,
                    origin_longitude=rec.pickup_partner_id.partner_longitude,
                    destination_latitude=rec.delivery_partner_id.partner_latitude,
                    destination_longitude=rec.delivery_partner_id.partner_longitude,
                    currency_id=currency.id,
                    evidence=local_estimation_evidence(history_records),
                )
            except FreightCoordinateError as exc:
                proposal = None
                failure_code = f"coordinate_evidence_gap:{exc}"
            history_count = len(history_records)
            if proposal:
                status = proposal.status
                failure_code = proposal.failure_code
                geometry_status = "available"
                request_fingerprint = proposal.request_fingerprint
                evidence_summary = {
                    **proposal.evidence_summary,
                    "executed_evidence": bounded_evidence_payload(history_records),
                }
                reasoning_summary = proposal.reasoning_summary
            else:
                status = "insufficient_evidence"
                geometry_status = "missing_or_invalid"
                request_fingerprint = hashlib.sha256(
                    f"estimate:{context.fingerprint}:{history_count}:{failure_code}".encode()
                ).hexdigest()
                evidence_summary = {
                    "estimator": ESTIMATOR_MODEL_VERSION,
                    "candidate_evidence_count": history_count,
                    "coordinate_quality": "missing_or_invalid",
                    "exact_lane_executed_count": None,
                    "executed_evidence": bounded_evidence_payload(history_records),
                }
                reasoning_summary = {"formula": "haversine", "reason": failure_code}
            prepared.append(
                {
                    "load": rec,
                    "correlation_id": correlation_id,
                    "context": context,
                    "estimate_proposal": proposal,
                    "status": status,
                    "failure_code": failure_code,
                    "history_count": history_count,
                    "request_fingerprint": request_fingerprint,
                    "values": {
                        "context_fingerprint": context.fingerprint,
                        "request_fingerprint": request_fingerprint,
                        "fingerprint_version": FREIGHT_CONTEXT_VERSION,
                        "source_model": PLASTICOS_LOAD,
                        "source_record_id": rec.id,
                        "origin_partner_id": rec.pickup_partner_id.id,
                        "destination_partner_id": rec.delivery_partner_id.id,
                        "expected_weight_lbs": rec.reference_weight,
                        "haversine_miles": proposal.haversine_miles if proposal else False,
                        "geometry_status": geometry_status,
                        "estimate_floor": proposal.estimate_floor if proposal else False,
                        "estimate_target": proposal.estimate_target if proposal else False,
                        "estimate_ceiling": proposal.estimate_ceiling if proposal else False,
                        "pricing_assumption": proposal.pricing_assumption if proposal else False,
                        "currency_id": proposal.currency_id if proposal else False,
                        "confidence": proposal.confidence if proposal else False,
                        "method": proposal.method if proposal else False,
                        "model_version": ESTIMATOR_MODEL_VERSION,
                        "policy_version": ESTIMATOR_POLICY_VERSION,
                        "evidence_summary": evidence_summary,
                        "reasoning_summary": reasoning_summary,
                        "failure_code": failure_code,
                        "status": status,
                    },
                }
            )
        existing = set()
        if prepared:
            rows = self.env["plasticos.freight.estimate"].search(
                [
                    ("source_model", "=", PLASTICOS_LOAD),
                    ("source_record_id", "in", [item["load"].id for item in prepared]),
                ]
            )
            existing = {
                (row.source_model, row.source_record_id, row.context_fingerprint, row.request_fingerprint)
                for row in rows
            }
        missing = [
            item
            for item in prepared
            if (
                PLASTICOS_LOAD,
                item["load"].id,
                item["context"].fingerprint,
                item["request_fingerprint"],
            )
            not in existing
        ]
        if not missing:
            return True
        created = create_freight_evidence_rows(
            self.env,
            "plasticos.freight.estimate",
            [(item["load"], item["values"]) for item in missing],
        )
        by_load = {row.source_record_id: row for row in created}
        events = []
        for item in missing:
            rec = item["load"]
            proposal = item["estimate_proposal"]
            status = item["status"]
            failure_code = item["failure_code"]
            estimate = by_load[rec.id]
            rec.message_post(
                body=(
                    f"Freight estimate {estimate.name} recorded as {status} using the local Haversine-curve policy. "
                    "It is nonbinding and does not assign a carrier or confirm a rate."
                )
            )
            events.append(
                {
                    "event_type": (
                        "freight_estimate_persisted" if status == "succeeded" else "freight_estimate_rejected"
                    ),
                    "outcome_code": failure_code or "local_haversine_curve",
                    "load": rec,
                    "facts": {
                        "estimate_id": estimate.id,
                        "exact_lane_evidence_count": (
                            proposal.evidence_summary["exact_lane_executed_count"] if proposal else None
                        ),
                        "similar_lane_evidence_count": (
                            proposal.evidence_summary["similar_lane_executed_count"] if proposal else None
                        ),
                        "candidate_evidence_count": item["history_count"],
                    },
                    "unknowns": [] if status == "succeeded" else [failure_code],
                    "correlation_id": item["correlation_id"],
                }
            )
        record_freight_events(self.env, events)
        return True

    def action_view_freight_quote_requests(self):
        action_record = self.env.ref("plasticos_logistics.action_freight_quote_request", raise_if_not_found=False)
        if not action_record:
            raise UserError("Freight quote request action is unavailable; upgrade plasticos_logistics.")
        action = action_record.read()[0]
        action["domain"] = [("load_id", "in", self.ids)]
        action["context"] = {"default_load_id": self.id if len(self) == 1 else False}
        return action

    def _latest_succeeded_estimates(self, specs):
        """First succeeded estimate per load after ``generated_at desc, id desc`` that matches its spec."""
        if not specs:
            return {}
        rows = self.env["plasticos.freight.estimate"].search(
            [
                ("source_model", "=", PLASTICOS_LOAD),
                ("source_record_id", "in", list(specs)),
                ("status", "=", "succeeded"),
            ],
            order="generated_at desc, id desc",
        )
        chosen = {}
        for estimate in rows:
            load_id = estimate.source_record_id
            if load_id in chosen:
                continue
            context, currency = specs[load_id]
            if estimate.context_fingerprint == context.fingerprint and estimate.currency_id == currency:
                chosen[load_id] = estimate
        return chosen

    def _latest_calibration_rows(self):
        """First calibration row per load after ``observed_at desc, id desc``."""
        if not self:
            return {}
        rows = self.env["plasticos.freight.calibration.observation"].search(
            [("load_id", "in", self.ids)],
            order="observed_at desc, id desc",
        )
        latest = {}
        for row in rows:
            latest.setdefault(row.load_id.id, row)
        return latest

    def action_record_actual_freight_cost(self):
        """Persist a non-mutating calibration observation from a verified actual cost."""
        from odoo.addons.plasticos_logistics.models.freight_governance import (
            create_freight_evidence_rows,
            record_freight_events,
        )
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        for rec in self:
            rec._require_freight_operator()
        self._lock_freight_advisories("actual-cost")
        self.invalidate_recordset()
        ready = []
        for rec in self:
            correlation_id = new_correlation_id()
            context = build_freight_context(rec)
            if not context or rec.actual_freight_cost is None or rec.actual_freight_cost < 0:
                raise UserError("A current freight context and non-negative actual freight cost are required.")
            currency = rec.actual_freight_currency_id or rec.rate_currency_id
            if not currency:
                raise UserError("Actual freight currency is required.")
            ready.append((rec, correlation_id, context, currency))
        if not ready:
            return True
        existing_ids = set(
            self.env["plasticos.freight.calibration.observation"]
            .search([("load_id", "in", [rec.id for rec, _correlation_id, _context, _currency in ready])])
            .mapped("load_id")
            .ids
        )
        for rec, _correlation_id, _context, _currency in ready:
            if rec.id in existing_ids:
                raise UserError("Actual freight calibration evidence already exists for this load.")
        chosen = self._latest_succeeded_estimates(
            {rec.id: (context, currency) for rec, _correlation_id, context, currency in ready}
        )
        pairs = []
        events = []
        recorded_at = fields.Datetime.now()
        for rec, correlation_id, context, currency in ready:
            estimate = chosen.get(rec.id)
            pairs.append(
                (
                    rec,
                    {
                        "load_id": rec.id,
                        "estimate_id": estimate.id if estimate else False,
                        "selected_quote_id": rec.selected_freight_quote_id.id
                        if rec.selected_freight_quote_id
                        else False,
                        "currency_id": currency.id,
                        "estimate_amount": estimate.estimate_target if estimate else False,
                        "booked_rate_amount": rec.rate_amount if rec.rate_currency_id == currency else False,
                        "actual_cost_amount": rec.actual_freight_cost,
                        "estimate_to_actual_variance": (
                            rec.actual_freight_cost - estimate.estimate_target if estimate else False
                        ),
                        "booked_to_actual_variance": (
                            rec.actual_freight_cost - rec.rate_amount if rec.rate_currency_id == currency else False
                        ),
                        "context_fingerprint": context.fingerprint,
                    },
                )
            )
            events.append(
                {
                    "event_type": "freight_actual_recorded",
                    "outcome_code": "recorded",
                    "load": rec,
                    "facts": {"currency_id": currency.id},
                    "correlation_id": correlation_id,
                }
            )
        create_freight_evidence_rows(self.env, "plasticos.freight.calibration.observation", pairs)
        for rec, _correlation_id, _context, _currency in ready:
            rec._freight_write({"actual_freight_recorded_at": recorded_at})
        record_freight_events(self.env, events)
        return True

    def action_correct_actual_freight_cost(self, actual_cost, currency, reason):
        """Append an attributed calibration correction without reopening prior evidence."""
        from odoo.addons.plasticos_logistics.models.freight_governance import (
            create_freight_evidence_rows,
            record_freight_events,
        )
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        if actual_cost is None or actual_cost < 0 or not currency or not reason:
            raise ValidationError("Actual-cost corrections require a non-negative amount, currency, and reason.")
        for rec in self:
            rec._require_freight_operator()
        self._lock_freight_advisories("actual-cost")
        self.invalidate_recordset()
        latest = self._latest_calibration_rows()
        prepared = []
        for rec in self:
            correlation_id = new_correlation_id()
            prior = latest.get(rec.id)
            if not prior:
                raise UserError("Record the initial actual freight cost before creating a correction.")
            context = build_freight_context(rec)
            if not context:
                raise UserError("A current freight context is required before correcting actual freight cost.")
            prepared.append((rec, correlation_id, prior, context))
        if not prepared:
            return True
        pairs = []
        events = []
        recorded_at = fields.Datetime.now()
        for rec, correlation_id, prior, context in prepared:
            pairs.append(
                (
                    rec,
                    {
                        "load_id": rec.id,
                        "estimate_id": prior.estimate_id.id if prior.estimate_id else False,
                        "selected_quote_id": rec.selected_freight_quote_id.id
                        if rec.selected_freight_quote_id
                        else False,
                        "currency_id": currency.id,
                        "estimate_amount": prior.estimate_amount if prior.currency_id == currency else False,
                        "booked_rate_amount": rec.rate_amount if rec.rate_currency_id == currency else False,
                        "actual_cost_amount": actual_cost,
                        "estimate_to_actual_variance": (
                            actual_cost - prior.estimate_amount
                            if prior.estimate_id and prior.currency_id == currency
                            else False
                        ),
                        "booked_to_actual_variance": (
                            actual_cost - rec.rate_amount if rec.rate_currency_id == currency else False
                        ),
                        "context_fingerprint": context.fingerprint,
                        "supersedes_observation_id": prior.id,
                        "correction_reason": reason,
                    },
                )
            )
            events.append(
                {
                    "event_type": "freight_actual_corrected",
                    "outcome_code": "superseded",
                    "load": rec,
                    "facts": {"currency_id": currency.id, "supersedes_observation_id": prior.id},
                    "correlation_id": correlation_id,
                }
            )
        create_freight_evidence_rows(self.env, "plasticos.freight.calibration.observation", pairs)
        for rec, _correlation_id, _prior, _context in prepared:
            rec._freight_write(
                {
                    "actual_freight_cost": actual_cost,
                    "actual_freight_currency_id": currency.id,
                    "actual_freight_recorded_at": recorded_at,
                }
            )
        record_freight_events(self.env, events)
        return True

    def action_open_actual_freight_correction_wizard(self):
        self.ensure_one()
        self._require_freight_operator()
        return {
            "type": "ir.actions.act_window",
            "name": "Correct Actual Freight",
            "res_model": "plasticos.freight.actual.correction.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_load_id": self.id,
                "default_actual_cost": self.actual_freight_cost,
                "default_currency_id": self.actual_freight_currency_id.id,
            },
        }

    def action_view_freight_estimates(self):
        action_record = self.env.ref("plasticos_logistics.action_freight_estimate", raise_if_not_found=False)
        if not action_record:
            raise UserError("Freight estimate action is unavailable; upgrade plasticos_logistics.")
        action = action_record.read()[0]
        action["domain"] = [("source_model", "=", PLASTICOS_LOAD), ("source_record_id", "in", self.ids)]
        return action

    def action_confirm_rate(self, rate=None):
        """Confirm a manually supplied rate through the canonical rate path.

        An intake-backed load keeps its legacy v3 context. A buyerless or manual
        load with no repeat stream uses the separately versioned manual context:
        the missing stream makes Same As Last ineligible, not the manual rate.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import select_manual_rate_context

        for rec in self:
            rec._require_freight_operator()
            context = select_manual_rate_context(rec)
            if not context:
                raise UserError("A complete freight context is required before confirming a manual rate.")
            rec._confirm_freight_rate(
                rate=rate if rate is not None else rec.rate_amount,
                carrier=rec.carrier_id,
                currency=rec.rate_currency_id,
                resolution_method="manual",
                context_fingerprint=context.fingerprint,
                context_version=context.version,
            )

    _RFQ_CANCEL_EVENT_TYPES = {
        "context_changed": "rfq_request_cancelled_context_change",
        "load_rate_confirmed": "rfq_request_cancelled_rate_confirmed",
    }

    def _cancel_stale_freight_quote_requests(
        self, current_fingerprint, correlation_id, reason="context_changed", exclude_request_ids=()
    ):
        """Cancel active RFQ episodes that can no longer be used for this load.

        With ``current_fingerprint`` set, only episodes whose freight context
        differs are cancelled (``reason="context_changed"``). With ``None`` every
        active episode is cancelled (``reason="load_rate_confirmed"``: the load
        has a confirmed rate, so any episode still active is orphaned).
        ``exclude_request_ids`` keeps the episode that is itself being resolved.
        Called from a transaction that succeeds (freight resolution or rate
        confirmation), so the cancellation and its audit event persist.
        Request-level guards only refuse stale requests; they never write,
        because their ``UserError`` rolls back.
        """
        from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_events

        event_type = self._RFQ_CANCEL_EVENT_TYPES[reason]
        if not self:
            return
        domain = [("load_id", "in", self.ids), ("state", "in", ("draft", "sent", "collecting"))]
        if current_fingerprint:
            domain.append(("context_fingerprint", "!=", current_fingerprint))
        if exclude_request_ids:
            domain.append(("id", "not in", list(exclude_request_ids)))
        stale = self.env["plasticos.freight.quote.request"].search(domain)
        if not stale:
            return
        stale._rfq_write(
            {
                "state": "cancelled",
                "cancelled_at": fields.Datetime.now(),
                "cancellation_reason": reason,
            }
        )
        record_freight_events(
            self.env,
            [
                {
                    "event_type": event_type,
                    "outcome_code": reason,
                    "load": request.load_id,
                    "facts": {
                        "request_id": request.id,
                        "stale_fingerprint": request.context_fingerprint,
                        "current_fingerprint": current_fingerprint,
                    },
                    "correlation_id": correlation_id,
                }
                for request in stale
            ],
        )

    def action_resolve_freight(self):
        """Resolve Same As Last deterministically; never creates an RFQ on a miss.

        The live RFQ workflow is intentionally unavailable until its recipient
        policy and delivery contract are accepted. A miss is persisted as a
        useful operator-visible outcome rather than silently falling back.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import FREIGHT_CONTEXT_VERSION
        from odoo.addons.plasticos_logistics.services.sal_resolver import resolve_sal

        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            rec.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.sal:{rec.id}"])
            rec.invalidate_recordset()
            # After the lock, a concurrent Resolve Freight may already have
            # confirmed this load. Keep that first result — do not reevaluate
            # (resolve_sal would return not_eligible and the miss branch would
            # overwrite SAL provenance while leaving the reused rate in place).
            if rec.rate_confirmed_at or rec.state == "rate_confirmed":
                # A confirmed load cannot be re-resolved, so any RFQ episode still
                # active on it is orphaned. Cancel it here, durably, so the
                # request-level guard's advice ("re-run Resolve Freight") always
                # leads to a persisted outcome whatever the load state.
                rec._cancel_stale_freight_quote_requests(None, correlation_id, reason="load_rate_confirmed")
                continue
            decision = resolve_sal(rec)
            # Persist the cancellation of RFQ episodes whose context no longer
            # matches. This transaction succeeds, so unlike the request-level
            # guard (which must raise) the cancellation is durable.
            rec._cancel_stale_freight_quote_requests(decision.context_fingerprint, correlation_id)
            values = {
                "freight_context_fingerprint": decision.context_fingerprint,
                "freight_context_version": FREIGHT_CONTEXT_VERSION if decision.context_fingerprint else False,
                "sal_decision": decision.decision,
                "sal_evaluated_at": fields.Datetime.now(),
                "sal_miss_reason": decision.reason if decision.decision != "hit" else False,
            }
            if decision.decision == "hit":
                source = self.browse(decision.source_load_id).exists()
                rec._confirm_freight_rate(
                    rate=source.rate_amount,
                    carrier=source.carrier_id,
                    currency=source.rate_currency_id,
                    resolution_method="sal",
                    context_fingerprint=decision.context_fingerprint,
                    sal_source_load=source,
                )
                rec.message_post(
                    body=(
                        f"SAL applied from load {source.name}: reused the current eligible carrier and booked rate. "
                        "No carrier RFQ was created."
                    )
                )
            else:
                rec._freight_write(values)
                rec.message_post(body=f"SAL {decision.decision}: {decision.reason or 'no qualifying history'}.")
                from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

                record_freight_event(
                    rec.env,
                    event_type="sal_miss" if decision.decision == "miss" else "sal_not_eligible",
                    outcome_code=decision.reason or decision.decision,
                    load=rec,
                    facts={"context_fingerprint": decision.context_fingerprint},
                    correlation_id=correlation_id,
                )
        return True

    def _confirm_freight_rate(
        self,
        rate,
        carrier,
        currency,
        resolution_method,
        context_fingerprint=None,
        sal_source_load=None,
        resolving_request=None,
        context_version=None,
    ):
        """Single serialized state-machine convergence point for all freight rates.

        ``resolving_request`` is the RFQ episode whose selected quote produced this
        confirmation; it is left for the caller to resolve while every other
        active episode on the load is cancelled as orphaned.
        ``context_version`` defaults to the legacy v3 context. Only a manual rate
        may use the manual context; SAL and live quotes stay on v3.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_MANUAL_VERSION,
            FREIGHT_CONTEXT_VERSION,
            build_freight_context_for_version,
        )

        context_version = context_version or FREIGHT_CONTEXT_VERSION
        if context_version == FREIGHT_CONTEXT_MANUAL_VERSION and resolution_method != "manual":
            raise ValidationError("A manual freight context cannot confirm a Same As Last or quoted rate.")

        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            rec.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.rate:{rec.id}"])
            rec.invalidate_recordset()
            if rec.state != "ready_confirmed":
                raise UserError("Freight rate confirmation requires a Ready Confirmed load.")
            if resolution_method not in {"manual", "sal", "live_quote"}:
                raise ValidationError("Freight resolution method is not supported.")
            if not rate or rate <= 0:
                raise ValidationError("Confirmed freight rate must be positive.")
            if not carrier or not currency:
                raise ValidationError("Confirmed freight requires an eligible carrier and explicit currency.")
            if not carrier.active or getattr(carrier, "entity_status", None) == "blocked":
                raise ValidationError("Confirmed freight carrier is inactive or blocked.")
            company = getattr(rec, "company_id", False) or (
                rec.sale_order_id.company_id if rec.sale_order_id else False
            )
            carrier_company = getattr(carrier, "company_id", False)
            if carrier_company and company and carrier_company != company:
                raise ValidationError("Confirmed freight carrier belongs to a different company.")
            current_context = build_freight_context_for_version(rec, context_version)
            if not current_context or not context_fingerprint or current_context.fingerprint != context_fingerprint:
                raise ValidationError("Freight context changed or is incomplete; rate confirmation is blocked.")
            if resolution_method == "sal" and not sal_source_load:
                raise ValidationError("SAL confirmation requires a qualifying source load.")
            values = {
                "carrier_id": carrier.id if carrier else False,
                "freight_context_fingerprint": context_fingerprint,
                "freight_context_version": context_version,
                "rate_amount": rate,
                "rate_auto_reused": resolution_method == "sal",
                "rate_confirmed_at": fields.Datetime.now(),
                "rate_currency_id": currency.id if currency else False,
                "rate_resolution_method": resolution_method,
                "sal_decision": "hit" if resolution_method == "sal" else rec.sal_decision,
                "sal_evaluated_at": fields.Datetime.now() if resolution_method == "sal" else rec.sal_evaluated_at,
                "sal_miss_reason": False if resolution_method == "sal" else rec.sal_miss_reason,
                "sal_source_load_id": sal_source_load.id if sal_source_load else False,
            }
            rec._freight_write(values)
            rec._transition("rate_confirmed", correlation_id=correlation_id)
            # A confirmed rate makes every other active RFQ episode on this load
            # orphaned; cancel them inside this successful transaction so the
            # cleanup does not depend on an operator re-running Resolve Freight
            # (whose button is hidden once the load leaves Ready Confirmed).
            rec._cancel_stale_freight_quote_requests(
                None,
                correlation_id,
                reason="load_rate_confirmed",
                exclude_request_ids=resolving_request.ids if resolving_request else (),
            )
            from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

            record_freight_event(
                rec.env,
                event_type="freight_rate_confirmed",
                outcome_code=resolution_method,
                load=rec,
                facts={
                    "carrier_id": carrier.id,
                    "currency_id": currency.id,
                    "sal_source_load_id": sal_source_load.id if sal_source_load else None,
                    "context_version": context_version,
                },
                correlation_id=correlation_id,
            )

    def _schedule_minimum_net_weight(self):
        self.ensure_one()
        if not self.transaction_id or not self.transaction_id.minimum_net_weight:
            return None
        return self.transaction_id.minimum_net_weight

    def _light_load_guard(self, override_reason):
        """Refuse Linda a light load. A person continues only with a recorded reason."""
        from ..schedule_window import OVERRIDE, light_load_decision
        from .linda_approval import is_linda

        self.ensure_one()
        linda = is_linda(self.env)
        decision = light_load_decision(
            linda,
            self.ready_net_weight_lbs or None,
            self._schedule_minimum_net_weight(),
            None if linda else override_reason,
        )
        if decision == "refuse":
            raise UserError(
                f"Load {self.name} is below the transaction minimum net weight. Linda cannot schedule or dispatch it."
            )
        if decision == "need_reason":
            raise UserError(
                f"Load {self.name} is below the transaction minimum net weight. A recorded reason is required."
            )
        if decision == OVERRIDE:
            self.light_load_override_reason = (override_reason or "").strip()

    def action_schedule(self, pickup_dt, delivery_dt, light_load_override_reason=None):
        """Schedule the load. Linda is held on the S11 gate. A light load refuses her."""
        from .linda_approval import linda_acting, linda_stop

        stop = linda_stop(self.env)
        if stop:
            return stop
        if linda_acting(self.env):
            return self._linda_schedule_gate(pickup_dt, delivery_dt)
        for rec in self:
            rec._apply_schedule(pickup_dt, delivery_dt, light_load_override_reason)

    def _apply_schedule(self, pickup_dt, delivery_dt, light_load_override_reason):
        self.ensure_one()
        self._require_freight_operator()
        self._light_load_guard(light_load_override_reason)
        self._require_physical_release("schedule")
        self.pickup_datetime = pickup_dt
        self.delivery_datetime = delivery_dt
        self._transition("scheduled")

    def _linda_schedule_gate(self, pickup_dt, delivery_dt):
        from ..schedule_window import REFUSE, light_load_decision
        from .linda_approval import hold_for_approval, prior_refusal, record_refusal

        held = []
        for rec in self:
            rec.check_access("read")
            if not rec.company_id:
                held.append(
                    {"status": "blocked", "record_id": rec.id, "reason": f"Load {rec.name} needs its proven company"}
                )
                continue
            arguments = {"load_id": rec.id, "pickup_dt": pickup_dt, "delivery_dt": delivery_dt}
            subject_key = f"load:{rec.id}"
            decision = light_load_decision(
                True, rec.ready_net_weight_lbs or None, rec._schedule_minimum_net_weight(), None
            )
            if decision == REFUSE:
                result = {"status": "blocked", "record_id": rec.id, "reason": "light_load"}
                held.append(
                    record_refusal(
                        self.env,
                        "schedule_load",
                        subject_key,
                        rec.company_id,
                        result,
                        arguments,
                        f"schedule_load:{rec.id}",
                        rec,
                    )
                )
                continue
            retry = prior_refusal(self.env, "schedule_load", subject_key, rec.company_id)
            held.append(
                hold_for_approval(
                    self.env,
                    "schedule_load",
                    "refusal_retry" if retry else "acceptance",
                    f"Linda schedules load {rec.name}",
                    arguments,
                    f"schedule_load:{rec.id}",
                    rec.company_id,
                    rec,
                    subject_key=subject_key,
                )
            )
        return held[0] if len(held) == 1 else held

    def action_dispatch(self, light_load_override_reason=None):
        """Dispatch load to carrier. Linda is held on the S11 gate. A light load refuses her."""
        from .linda_approval import linda_acting, linda_stop

        stop = linda_stop(self.env)
        if stop:
            return stop
        if linda_acting(self.env):
            return self._linda_dispatch_gate()
        for rec in self:
            rec._apply_dispatch(light_load_override_reason)

    def _apply_dispatch(self, light_load_override_reason):
        self.ensure_one()
        self._require_freight_operator()
        self._light_load_guard(light_load_override_reason)
        self._require_physical_release("dispatch")
        if self.state != "scheduled":
            raise UserError(f"Load {self.name} must be in Scheduled state before dispatch.")
        if not self.carrier_id:
            raise UserError(f"Load {self.name}: Carrier is required before dispatch.")
        if not self.pickup_partner_id:
            raise UserError(f"Load {self.name}: Pickup location is required before dispatch.")
        if not self.delivery_partner_id:
            raise UserError(f"Load {self.name}: Delivery location is required before dispatch.")
        if not self.pickup_datetime:
            raise UserError(f"Load {self.name}: Pickup date/time is required before dispatch.")
        self._transition("dispatched")

    def _linda_dispatch_gate(self):
        from ..schedule_window import REFUSE, light_load_decision
        from .linda_approval import hold_for_approval, prior_refusal, record_refusal

        held = []
        for rec in self:
            rec.check_access("read")
            if not rec.company_id:
                held.append(
                    {"status": "blocked", "record_id": rec.id, "reason": f"Load {rec.name} needs its proven company"}
                )
                continue
            arguments = {"load_id": rec.id}
            subject_key = f"load:{rec.id}"
            decision = light_load_decision(
                True, rec.ready_net_weight_lbs or None, rec._schedule_minimum_net_weight(), None
            )
            if decision == REFUSE:
                result = {"status": "blocked", "record_id": rec.id, "reason": "light_load"}
                held.append(
                    record_refusal(
                        self.env,
                        "dispatch_load",
                        subject_key,
                        rec.company_id,
                        result,
                        arguments,
                        f"dispatch_load:{rec.id}",
                        rec,
                    )
                )
                continue
            retry = prior_refusal(self.env, "dispatch_load", subject_key, rec.company_id)
            held.append(
                hold_for_approval(
                    self.env,
                    "dispatch_load",
                    "refusal_retry" if retry else "acceptance",
                    f"Linda dispatches load {rec.name}",
                    arguments,
                    f"dispatch_load:{rec.id}",
                    rec.company_id,
                    rec,
                    subject_key=subject_key,
                )
            )
        return held[0] if len(held) == 1 else held

    def _open_rebook_activity(self):
        """One open activity asking for the pickup to be rebooked (BRS-03-R022)."""
        self.ensure_one()
        summary = "Rebook pickup appointment"
        existing = (
            self.env["mail.activity"]
            .sudo()
            .search([("res_model", "=", self._name), ("res_id", "=", self.id), ("summary", "=", summary)], limit=1)
        )
        if existing:
            return existing
        return self.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=self.env.user.id,
            summary=summary,
            note="The accepted delivery slot changed. Rebook the pickup appointment.",
        )

    _FREIGHT_CONTEXT_STALE_MESSAGE = (
        "Freight context changed after rate confirmation. Scheduling and dispatch are blocked until an "
        "approved logistics recovery action resolves the exception."
    )

    def _freight_context_is_stale(self):
        """True when the confirmed lane no longer matches the context version it recorded.

        The recorded ``freight_context_version`` selects the validator, so an
        accepted v3 fingerprint is never rehashed as a manual context or the reverse.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context_for_version,
        )

        self.ensure_one()
        if not self.rate_resolution_method or not self.freight_context_fingerprint:
            return False
        version = self.freight_context_version or FREIGHT_CONTEXT_VERSION
        current_context = build_freight_context_for_version(self, version)
        return not current_context or current_context.fingerprint != self.freight_context_fingerprint

    def _ensure_sal_context_current(self):
        """Fail closed when any confirmed freight lane has materially changed."""
        for rec in self:
            if rec._freight_context_is_stale():
                raise UserError(self._FREIGHT_CONTEXT_STALE_MESSAGE)

    # ── Physical-operation release guard (C03, BRS-EXP-10-R004/R008) ──

    def _physical_release_errors(self, operation_kind):
        """Reasons this load may not receive a NEW physical instruction.

        Downstream owners (Documents evidence policy, Export booking holds) extend
        this by ordinary inheritance and append their own reasons. Recording an
        event that already happened is never routed through here.
        """
        self.ensure_one()
        errors = []
        if self._freight_context_is_stale():
            errors.append(self._FREIGHT_CONTEXT_STALE_MESSAGE)
        return errors

    def _require_physical_release(self, operation_kind):
        """Raise when any owner withholds this new physical instruction."""
        if operation_kind not in PHYSICAL_RELEASE_OPERATIONS:
            raise ValidationError(f"Unknown physical operation {operation_kind!r}.")
        for rec in self:
            errors = rec._physical_release_errors(operation_kind)
            if errors:
                raise UserError("\n".join(errors))

    @api.model
    def assert_can_release_physical_operation(self, load_id, operation_kind, expected_context_token=None):
        """Frozen Logistics command: may this load receive a new physical instruction now?

        Returns ``applied`` when every owner allows it, ``blocked`` with the joined
        reasons, ``stale`` when the caller's freight-context token no longer
        matches, and ``not_available`` for a missing load or unknown operation.
        It writes nothing.
        """
        if operation_kind not in PHYSICAL_RELEASE_OPERATIONS:
            return {"status": "not_available", "reason": f"unknown operation {operation_kind!r}"}
        load = self.browse(load_id).exists()
        if not load:
            return {"status": "not_available", "reason": "load not found"}
        load.check_access("read")
        if expected_context_token and expected_context_token != load.freight_context_fingerprint:
            return {"status": "stale", "record_id": load.id, "reason": "freight context token changed"}
        errors = load._physical_release_errors(operation_kind)
        if errors:
            return {"status": "blocked", "record_id": load.id, "reason": "\n".join(errors)}
        return {"status": "applied", "record_id": load.id}

    def action_close(self):
        for rec in self:
            rec._require_freight_operator()
            if not rec.bol_pickup_attached or not rec.bol_delivery_attached:
                raise UserError("BOL documents required.")
            rec._transition("closed")

    # ── Actual physical event clocks (C03, BRS-EXP-04-R003, BRS-EXP-10-R007) ──

    def _require_actual_event_attachment(self, attachment):
        """The evidence must be an original attached to this load, in its company."""
        self.ensure_one()
        attachment = attachment.exists() if attachment else attachment
        if not attachment:
            raise UserError("An actual pickup or delivery needs the original document that attests it.")
        from .linda_approval import original_hidden

        if not self.env.su and original_hidden(self.env, attachment):
            # R9: an original the caller cannot see is refused without naming it, for every caller.
            raise AccessError(ORIGINAL_NOT_VISIBLE)
        if attachment.res_model != PLASTICOS_LOAD or attachment.res_id != self.id:
            raise ValidationError(
                f"The evidence is not attached to load {self.name}. Attach the original to this load first."
            )
        if attachment.company_id and attachment.company_id != self.company_id:
            raise ValidationError("Actual-event evidence must belong to the load's company.")
        return attachment

    def action_record_actual_event(self, event_kind, occurred_at, attachment, reason=None):
        """Record an actual pickup or delivery that already happened, from its evidence.

        Recording what happened is separate from releasing a new instruction: it is
        allowed whatever later booking or freight change withholds new release.
        A first record needs evidence attached to this load. Repeating the same
        time and evidence is a no-op. A different value is a correction, which
        needs a reason and appends a correction event; the earlier event stays.
        Returns ``{"status": "applied" | "already_applied"}``.
        """
        from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

        self.ensure_one()
        if event_kind not in _ACTUAL_EVENT_KINDS:
            raise ValidationError(f"Unknown actual event {event_kind!r}; expected pickup or delivery.")
        from .linda_approval import linda_acting, linda_stop

        stop = linda_stop(self.env)
        if stop:
            return stop
        if linda_acting(self.env):
            return self._linda_actual_event_gate(event_kind, occurred_at, attachment, reason)
        self._require_freight_operator()
        if not self.company_id:
            raise UserError(f"Load {self.name} needs its proven company before an actual event is recorded.")
        occurred_at = fields.Datetime.to_datetime(occurred_at)
        if not occurred_at:
            raise UserError("The actual event time is required.")
        # Stored datetimes have whole seconds; compare a replay on the same precision.
        occurred_at = occurred_at.replace(microsecond=0)
        if occurred_at > fields.Datetime.now():
            raise ValidationError("An actual event cannot be in the future.")
        attachment = self._require_actual_event_attachment(attachment)
        self._lock_freight_advisories("actual-event")
        self.invalidate_recordset()
        time_field, evidence_field, event_type = _ACTUAL_EVENT_KINDS[event_kind]
        previous_at = self[time_field].replace(microsecond=0) if self[time_field] else self[time_field]
        previous_attachment = self[evidence_field]
        if previous_at == occurred_at and previous_attachment == attachment:
            return {"status": "already_applied", "record_id": self.id}
        explanation = (reason or "").strip()
        if previous_at and not explanation:
            raise UserError(f"Load {self.name} already has an actual {event_kind}. A correction needs a reason.")
        pickup_at = occurred_at if event_kind == "pickup" else self.actual_pickup_at
        delivery_at = occurred_at if event_kind == "delivery" else self.actual_delivery_at
        if pickup_at and delivery_at and delivery_at < pickup_at:
            raise ValidationError("Actual delivery cannot be before actual pickup.")
        self.with_context(**{_ACTUAL_EVENT_INTERNAL_WRITE: _ACTUAL_EVENT_INTERNAL_WRITE_TOKEN}).write(
            {time_field: occurred_at, evidence_field: attachment.id}
        )
        facts = {
            "event_kind": event_kind,
            "occurred_at": fields.Datetime.to_string(occurred_at),
            "evidence_attachment_id": attachment.id,
            "recorded_by_id": self.env.user.id,
        }
        if previous_at:
            facts.update(
                {
                    "previous_occurred_at": fields.Datetime.to_string(previous_at),
                    "previous_evidence_attachment_id": previous_attachment.id or None,
                    "correction_reason": explanation,
                }
            )
        record_freight_event(
            self.env,
            event_type="actual_event_corrected" if previous_at else event_type,
            outcome_code=event_kind,
            load=self,
            facts=facts,
            correlation_id=new_correlation_id(),
        )
        verb = "corrected" if previous_at else "recorded"
        self.message_post(body=f"Actual {event_kind} {verb}: {facts['occurred_at']} from {attachment.display_name}.")
        return {"status": "applied", "record_id": self.id}

    def _linda_actual_event_gate(self, event_kind, occurred_at, attachment, reason):
        """Linda's actual pickup or delivery (C12-SCOPE-3 (1)).

        A value that differs from the recorded one is a correction and is always held.
        A first record runs straight through unless it is out of sequence, lacks
        verified evidence or follows a refusal on this load; those are held. Any other
        refusal is returned as ``blocked`` and recorded, never raised.
        """
        from .linda_approval import as_approved, hold_for_approval, original_hidden, prior_refusal, record_refusal

        self.check_access("read")
        if not self.company_id:
            # R6: no company, no ledger subject; answered, never a raw required-field error.
            return {"status": "blocked", "record_id": self.id, "reason": f"Load {self.name} needs its proven company"}
        when = fields.Datetime.to_datetime(occurred_at) if occurred_at else None
        when = when.replace(microsecond=0) if when else None
        attachment_id = attachment.id if attachment else False
        command, subject_key = "record_actual_event", f"load:{self.id}"
        arguments = {
            "load_id": self.id,
            "event_kind": event_kind,
            "occurred_at": when,
            "attachment_id": attachment_id,
            "reason": reason,
        }
        stamp = fields.Datetime.to_string(when) if when else ""
        key = f"actual:{self.id}:{event_kind}:{stamp}:{attachment_id or 0}"
        time_field, evidence_field, _event_type = _ACTUAL_EVENT_KINDS[event_kind]
        previous_at = self[time_field].replace(microsecond=0) if self[time_field] else None
        edge, cause = None, None
        if previous_at and (previous_at != when or self[evidence_field].id != attachment_id):
            if not (reason or "").strip():
                # R5: a correction without a reason is refused before any hold, as for journey facts.
                refusal = {"status": "blocked", "record_id": self.id, "reason": "a correction needs a reason"}
                return record_refusal(self.env, command, subject_key, self.company_id, refusal, arguments, key, self)
            edge, cause = "correction", f"Linda corrects the recorded actual {event_kind}"
        elif original_hidden(self.env, attachment):
            # R2/N4: only the attachment check makes an unreadable original unverified evidence;
            # the reason names nothing of it.
            edge, cause = "evidence_unverified", "the original document is not visible to Linda"
        else:
            try:
                with self.env.cr.savepoint():
                    probe = as_approved(self).action_record_actual_event(event_kind, occurred_at, attachment, reason)
                    raise _LindaProbeRollback(probe)
            except _LindaProbeRollback as done:
                self.env.invalidate_all()
                if done.result.get("status") == "already_applied":
                    return done.result
            except (UserError, ValidationError, AccessError) as error:
                self.env.invalidate_all()
                message = str(error.args[0] if error.args else error)
                edge = _actual_event_edge(message)
                if not edge:
                    refusal = {"status": "blocked", "record_id": self.id, "reason": message}
                    return record_refusal(
                        self.env, command, subject_key, self.company_id, refusal, arguments, key, self
                    )
                cause = message
        if prior_refusal(self.env, command, subject_key, self.company_id):
            edge, cause = "refusal_retry", f"Linda's previous actual-event record on load {self.name} was refused"
        if not edge:
            return as_approved(self).action_record_actual_event(event_kind, occurred_at, attachment, reason)
        return hold_for_approval(
            self.env, command, edge, cause, arguments, key, self.company_id, self, subject_key=subject_key
        )

    def action_open_actual_event_wizard(self):
        self.ensure_one()
        self._require_freight_operator()
        return {
            "type": "ir.actions.act_window",
            "name": "Record Actual Event",
            "res_model": "plasticos.load.actual.event.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_load_id": self.id},
        }

    # ── Exact transaction binding (frozen Logistics command) ──────────

    @api.model
    def action_bind_exact_transaction_load(self, transaction_id, load_id, movement_authorization, operation_key):
        """Bind one load to its single parent transaction through the ordinary guarded write.

        ``movement_authorization`` names the route (``sale`` or ``purchase``) the
        caller relies on; a route the records do not support is refused. The parent
        link is ``plasticos.load.transaction_id``: one transaction may own many
        loads, and a load has at most one parent (ADR-130, amendment A1).
        """
        if not (operation_key or "").strip():
            return {"status": "blocked", "reason": "operation_key is required"}
        load = self.browse(load_id).exists()
        transaction = self.env[PLASTICOS_TRANSACTION].browse(transaction_id).exists()
        if not load or not transaction:
            return {"status": "not_available", "reason": "load or transaction not found"}
        load._require_freight_operator()
        if load.transaction_id == transaction:
            return {"status": "already_applied", "record_id": load.id}
        if load.transaction_id:
            return {"status": "blocked", "record_id": load.id, "reason": "load already has another transaction"}
        route = (movement_authorization or {}).get("route")
        actual_route = load._parent_route(transaction)
        if route != actual_route:
            return {
                "status": "blocked",
                "record_id": load.id,
                "reason": f"movement authorization route {route!r} does not match the {actual_route} route",
            }
        error = load._parent_identity_error(transaction) or load._join_milestone_error(transaction)
        if error:
            return {"status": "blocked", "record_id": load.id, "reason": error}
        load.write({"transaction_id": transaction.id})
        return {"status": "applied", "record_id": load.id}

    def _transition(self, new_state, *, correlation_id=None):
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
            # Every route that issues a new instruction meets the same guard here,
            # including the bulk wizard. picked_up/delivered record what happened.
            release = _RELEASE_STATES.get(new_state)
            if release:
                rec._require_physical_release(release)

            correlation_id = correlation_id or new_correlation_id()
            old = rec.state
            vals = {"state": new_state, "entered_state_at": fields.Datetime.now()}
            if new_state == "dispatched":
                vals["dispatched_at"] = fields.Datetime.now()
            if new_state == "delivered":
                vals["delivered_at"] = fields.Datetime.now()
            rec._freight_write(vals)
            from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

            record_freight_event(
                rec.env,
                event_type="freight_state_transition",
                outcome_code=new_state,
                load=rec,
                facts={"from_state": old, "to_state": new_state},
                correlation_id=correlation_id,
            )
            _logger.info("Load %s state transition: %s -> %s (correlation: %s)", rec.id, old, new_state, correlation_id)

    def _store_rate_memory(self):
        """Deprecated compatibility hook; legacy cache writes are permanently frozen."""
        _logger.warning(
            "Legacy rate-memory write skipped for load %s; canonical freight history owns new evidence.", self.id
        )
        return False

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

    def _escalate_sla_breach(self, level, hours, limit_hours):
        """Assign one SLA-breach Activity per load and breach level to an Operations Manager.

        Both SLA jobs call this, so a load breached at one level carries one open Activity
        however many jobs observe it. With no eligible manager the breach is logged and
        noted once on the load.
        """
        self.ensure_one()
        return self.env["res.users"]._plasticos_escalate_to_manager(
            self,
            OPERATIONS_MANAGER_GROUP,
            summary=f"ESCALATION: SLA breach [{level.upper()}] on {self.name}",
            note=(
                f"Load {self.name} has been in state '{self.state}' for {hours:.1f} hours "
                f"(limit: {limit_hours} hours). Manual intervention required."
            ),
            label=f"SLA breach {level} escalation",
            companies=self.company_id,
            exclude_users=self.transaction_id.user_id,
        )

    @api.model
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

    @api.model
    def _cron_check_dispatch_acknowledgments(self):
        """Escalate dispatches the carrier has not acknowledged within four hours.

        The clock is the recorded ``dispatch_sent`` (the confirmed send), and the
        job creates one internal escalation activity per load per day. It does not
        resend the full dispatch packet: a blind resend could repeat an
        instruction whose first delivery outcome is unknown (BRS-EXP-10-R004).

        The job polls every five minutes (S4, V10). Linda records the +2h carrier
        reminder and the +4h carrier and ops escalation as request obligations,
        once each per actual sent time and audience, and withholds one whose load
        no longer needs it. Neither carries the packet.
        """
        requests = self.env["plasticos.logistics.request"]
        requests.sudo()._run_load_obligations()  # cron-sudo-justification: sudo: only Linda's sudo writer records evidence
        threshold_hours = 4
        threshold_dt = fields.Datetime.now() - timedelta(hours=threshold_hours)

        domain = [
            ("dispatch_sent", "!=", False),
            ("dispatch_sent", "<", threshold_dt),
            ("dispatch_acknowledged", "=", False),
            ("state", "in", ["dispatched", "scheduled"]),
        ]
        # Test seam (S6, C06-SCOPE-3): the same context key narrows the Linda sweep.
        # Absent in production, where the domain is unchanged.
        scope = self.env.context.get("linda_load_sweep_ids")
        if scope is not None:
            domain.append(("id", "in", [int(load_id) for load_id in scope]))
        # An escalated load stays eligible until it is acknowledged, so a fixed oldest-first
        # page kept returning the loads escalated earlier today and never reached the newer
        # ones (S6 finding D9). Loads already escalated today are excluded before the page is
        # taken: each run handles the next page of 100, and no load is escalated twice a day.
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", PLASTICOS_LOAD),
                ("summary", "ilike", "URGENT: No carrier acknowledgment"),
                # activity_schedule dates the deadline in the user's timezone; compare in it too.
                ("date_deadline", "=", fields.Date.context_today(self)),
            ],
            order="id",
        )
        already_escalated = set(activities.mapped("res_id"))
        if already_escalated:
            domain.append(("id", "not in", sorted(already_escalated)))
        unacknowledged = self.search(domain, order="dispatch_sent asc", limit=100)

        for load in unacknowledged:
            if load.id in already_escalated:
                continue

            # Escalated to an Operations Manager in the load's company: never the salesperson,
            # never the user running the job. The day filter above is this site's idempotency.
            self.env["res.users"]._plasticos_escalate_to_manager(
                load,
                OPERATIONS_MANAGER_GROUP,
                summary=f"URGENT: No carrier acknowledgment for {load.name}",
                note=(
                    f"Carrier has not acknowledged dispatch sent {load.dispatch_sent}. "
                    "The dispatch packet was not resent automatically."
                ),
                label="carrier acknowledgment escalation",
                companies=load.company_id,
                one_open=False,
                exclude_users=load.transaction_id.user_id,
            )

        return True

    # ── Email Send Actions (Paperless) ──────────────────────────────

    def action_send_delivery_order(self):
        """Open email composer with Delivery Order attached."""
        self.ensure_one()
        self._require_physical_release("carrier_document")
        template = self._get_email_template("email_template_delivery_order")
        return self._open_mail_composer(template, operation="carrier_document")

    def action_send_bol_pickup(self):
        """Open email composer with BOL Pickup attached."""
        self.ensure_one()
        self._require_physical_release("carrier_document")
        template = self._get_email_template("email_template_bol_pickup")
        return self._open_mail_composer(template, operation="carrier_document")

    def action_send_bol_delivery(self):
        """Open email composer with BOL Delivery attached."""
        self.ensure_one()
        self._require_physical_release("carrier_document")
        template = self._get_email_template("email_template_bol_delivery")
        return self._open_mail_composer(template, operation="carrier_document")

    def action_send_dispatch_packet(self):
        """Open email composer with full dispatch packet (all 3 docs)."""
        self.ensure_one()
        self._require_physical_release("dispatch_packet")
        template = self._get_email_template("email_template_dispatch_packet")
        return self._open_mail_composer(template, operation="dispatch_packet")

    def _carrier_sender_error(self):
        """Why this load's company cannot be the sender of carrier mail, or ``False`` (S4, D5).

        Carrier mail is sent only from the load company's own address. Odoo 19 fills an
        empty rendered sender with a default one, so the absence is refused here.
        """
        self.ensure_one()
        company = self.company_id
        if not company or not email_normalize(company.email or ""):
            name = company.name if company else "(none)"
            return f"Company {name} of load {self.name} has no valid email address to send carrier mail from."
        return False

    def action_send_dispatch_direct(self):
        """Send the dispatch packet now; stamp ``dispatch_sent`` only on a confirmed send.

        Queueing is not sending. ``dispatch_sent`` is the acknowledgment clock, so it
        is stamped only when native mail reports the message sent. An exception or
        a still-queued message leaves it empty and says so in the chatter.
        """
        self.ensure_one()
        self._require_physical_release("dispatch_packet")
        if not self.carrier_id:
            raise UserError(f"Load {self.name}: Carrier is required to send dispatch.")
        if not self.carrier_id.email:
            raise UserError(f"Carrier {self.carrier_id.name} has no email address.")
        sender_error = self._carrier_sender_error()
        if sender_error:
            # Fail closed before any mail exists: Odoo would fill an empty sender with its own default.
            self.message_post(body=f"Dispatch packet not sent. {sender_error} Dispatch Sent was not stamped.")
            return False

        template = self._get_email_template("email_template_dispatch_packet")
        mail_id = template.send_mail(self.id, force_send=True)
        mail = self.env["mail.mail"].sudo().browse(mail_id).exists()  # sudo: read own mail outcome only
        # A force-sent mail with auto_delete is removed only after a successful send.
        if not mail or mail.state == "sent":
            # The first confirmed send is the acknowledgement clock and its revision key;
            # a later packet never moves it (S4, same property as the composer path).
            if not self.dispatch_sent:
                self.dispatch_sent = fields.Datetime.now()
            self.message_post(body="Dispatch packet sent to carrier.")
            return True
        self.message_post(
            body=(
                f"Dispatch packet not confirmed sent (mail state: {mail.state}). "
                "Dispatch Sent was not stamped; check the outgoing mail before acting again."
            )
        )
        return False

    def _notify_by_email_get_headers(self, *args, **kwargs):
        """Tag a carrier dispatch packet's notification mail with its own load (S4, V10).

        Only the composer sets the context key, and only while it sends a release
        packet; mail.mail then stamps ``dispatch_sent`` when native transport confirms
        a mail whose header names that same load. Queueing stamps nothing.
        """
        from .mail_mail_inherit import (
            DISPATCH_PACKET_HEADER,
            DISPATCH_PACKET_SEND_CONTEXT,
            DISPATCH_PACKET_VALUE,
        )

        headers = super()._notify_by_email_get_headers(*args, **kwargs)
        if self.env.context.get(DISPATCH_PACKET_SEND_CONTEXT) and len(self) == 1:
            headers[DISPATCH_PACKET_HEADER] = f"{DISPATCH_PACKET_VALUE}:{self.id}"
        return headers

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

    def _open_mail_composer(self, template, operation=None):
        """Helper to open mail composer wizard with template.

        ``operation`` names the physical release this composer carries. Opening it
        is not the authorization point: mail.compose.message re-checks the release
        guard when the composer actually sends (S4, D2).
        """
        ctx = {
            "default_model": PLASTICOS_LOAD,
            "default_res_ids": self.ids,
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
            "force_email": True,
        }
        if operation:
            ctx["plasticos_load_release_operation"] = operation
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
        tx = self.transaction_id
        if not tx:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": PLASTICOS_TRANSACTION,
            "res_id": tx.id,
            "view_mode": "form",
            "target": "current",
        }


class PlasticosLoadActualEventWizard(models.TransientModel):
    """Paperwork entry for an actual pickup or delivery; delegates to the load command."""

    _name = "plasticos.load.actual.event.wizard"
    _description = "Record Actual Load Event"

    load_id = fields.Many2one(PLASTICOS_LOAD, required=True, ondelete="cascade")
    event_kind = fields.Selection([("pickup", "Actual Pickup"), ("delivery", "Actual Delivery")], required=True)
    occurred_at = fields.Datetime(string="Happened At", required=True)
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Evidence",
        required=True,
        ondelete="cascade",
        domain="[('res_model', '=', 'plasticos.load'), ('res_id', '=', load_id)]",
        help="The original document attached to this load that attests the event.",
    )
    reason = fields.Text(help="Required when this corrects an event already recorded.")

    def action_confirm(self):
        self.ensure_one()
        self.load_id.action_record_actual_event(self.event_kind, self.occurred_at, self.attachment_id, self.reason)
        return {"type": "ir.actions.act_window_close"}

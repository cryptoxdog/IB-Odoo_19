import hashlib
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models
from odoo.addons.plasticos_logistics.services.state_machine import VALID_TRANSITIONS, new_correlation_id
from odoo.exceptions import AccessError, UserError, ValidationError

RES_PARTNER = "res.partner"
PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_LOAD = "plasticos.load"
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
)


class PlasticosLoad(models.Model):
    _name = "plasticos.load"
    _description = "Plasticos Logistics Load"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True, default=lambda self: self.env["ir.sequence"].next_by_code(PLASTICOS_LOAD) or "New"
    )
    sale_order_id = fields.Many2one("sale.order", ondelete="restrict")
    company_id = fields.Many2one(
        "res.company", related="sale_order_id.company_id", store=True, readonly=True, index=True, ondelete="restrict"
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

    pickup_datetime = fields.Datetime(string="Pickup Date/Time")
    delivery_datetime = fields.Datetime(string="Delivery Date/Time")

    bol_pickup_attached = fields.Boolean(default=False)
    bol_delivery_attached = fields.Boolean(default=False)

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

    def _parent_identity_error(self, transaction):
        """Refuse a new parent whose commercial identity is missing or different."""
        self.ensure_one()
        if not self.sale_order_id or not transaction.sale_order_id:
            return "A load and its transaction both need a sale order."
        if self.sale_order_id != transaction.sale_order_id:
            return "A load must use the same sale order as its transaction."
        load_company = self.company_id
        transaction_company = transaction.sale_order_id.company_id
        if bool(load_company) != bool(transaction_company) or (
            load_company and transaction_company and load_company != transaction_company
        ):
            return "A load cannot join a transaction across companies or with an unknown company."
        if not transaction.supplier_id or not transaction.buyer_id:
            return "Cannot link a load until the transaction has both a supplier and a buyer."
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
        freight_fields = set(vals)
        internal_freight_write = self.env.context.get(_FREIGHT_INTERNAL_WRITE) is _FREIGHT_INTERNAL_WRITE_TOKEN
        internal_scale_ticket_write = (
            self.env.context.get(_SCALE_TICKET_INTERNAL_WRITE) is _SCALE_TICKET_INTERNAL_WRITE_TOKEN
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
                }
                if internal_freight_write:
                    allowed.update(_FREIGHT_ACTUAL_INPUT_FIELDS | {"actual_freight_recorded_at"})
                if internal_scale_ticket_write:
                    allowed.update(_SCALE_TICKET_STATUS_FIELDS)
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

    @api.depends("delivery_term", "transaction_id.delivery_term")
    def _compute_delivery_term_overridden(self):
        """Check if delivery_term differs from the linked transaction."""
        for rec in self:
            tx = rec.transaction_id
            if tx and tx.delivery_term:
                rec.delivery_term_overridden = rec.delivery_term != tx.delivery_term
            else:
                rec.delivery_term_overridden = False

    @api.constrains("delivery_term", "delivery_term_override_reason")
    def _check_override_reason_required(self):
        """Require reason when delivery_term is overridden."""
        for rec in self:
            if rec.delivery_term_overridden and not rec.delivery_term_override_reason:
                raise ValidationError(
                    "Override reason is required when changing delivery term from transaction default."
                )

    def action_confirm_ready(self):
        """Confirm load is ready for pickup. Captures authenticated user."""
        for rec in self:
            rec._require_freight_operator()
            rec.ready_confirmed_by = self.env.user.name
            rec.ready_confirmed_at = fields.Datetime.now()
            rec._transition("ready_confirmed")

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
                    "proposal": proposal,
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
            proposal = item["proposal"]
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
        """Confirm a manually supplied rate through the canonical rate path."""
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        for rec in self:
            rec._require_freight_operator()
            context = build_freight_context(rec)
            if not context:
                raise UserError("A complete freight context is required before confirming a manual rate.")
            rec._confirm_freight_rate(
                rate=rate if rate is not None else rec.rate_amount,
                carrier=rec.carrier_id,
                currency=rec.rate_currency_id,
                resolution_method="manual",
                context_fingerprint=context.fingerprint,
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
    ):
        """Single serialized state-machine convergence point for all freight rates.

        ``resolving_request`` is the RFQ episode whose selected quote produced this
        confirmation; it is left for the caller to resolve while every other
        active episode on the load is cancelled as orphaned.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context,
        )

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
            current_context = build_freight_context(rec)
            if not current_context or not context_fingerprint or current_context.fingerprint != context_fingerprint:
                raise ValidationError("Freight context changed or is incomplete; rate confirmation is blocked.")
            if resolution_method == "sal" and not sal_source_load:
                raise ValidationError("SAL confirmation requires a qualifying source load.")
            values = {
                "carrier_id": carrier.id if carrier else False,
                "freight_context_fingerprint": context_fingerprint,
                "freight_context_version": FREIGHT_CONTEXT_VERSION,
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
                },
                correlation_id=correlation_id,
            )

    def action_schedule(self, pickup_dt, delivery_dt):
        for rec in self:
            rec._require_freight_operator()
            rec._ensure_sal_context_current()
            rec.pickup_datetime = pickup_dt
            rec.delivery_datetime = delivery_dt
            rec._transition("scheduled")

    def action_dispatch(self):
        """Dispatch load to carrier. Validates required fields before dispatch."""
        for rec in self:
            rec._require_freight_operator()
            rec._ensure_sal_context_current()
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

    def _ensure_sal_context_current(self):
        """Fail closed when any confirmed freight lane has materially changed."""
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        for rec in self:
            if not rec.rate_resolution_method or not rec.freight_context_fingerprint:
                continue
            current_context = build_freight_context(rec)
            if not current_context or current_context.fingerprint != rec.freight_context_fingerprint:
                raise UserError(
                    "Freight context changed after rate confirmation. Scheduling and dispatch are blocked until an "
                    "approved logistics recovery action resolves the exception."
                )

    def action_close(self):
        for rec in self:
            rec._require_freight_operator()
            if not rec.bol_pickup_attached or not rec.bol_delivery_attached:
                raise UserError("BOL documents required.")
            rec._transition("closed")

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
        """Check for unacknowledged dispatches and escalate.

        Creates escalation activity and resends dispatch email for loads
        where carrier has not acknowledged within threshold.
        """
        threshold_hours = 4
        threshold_dt = fields.Datetime.now() - timedelta(hours=threshold_hours)

        unacknowledged = self.search(
            [
                ("dispatch_sent", "!=", False),
                ("dispatch_sent", "<", threshold_dt),
                ("dispatch_acknowledged", "=", False),
                ("state", "in", ["dispatched", "scheduled"]),
            ],
            order="dispatch_sent asc",
            limit=100,
        )
        already_escalated = set()
        if unacknowledged:
            activities = self.env["mail.activity"].search(
                [
                    ("res_model", "=", PLASTICOS_LOAD),
                    ("res_id", "in", unacknowledged.ids),
                    ("summary", "ilike", "URGENT: No carrier acknowledgment"),
                    ("date_deadline", "=", fields.Date.today()),
                ],
                order="id",
            )
            already_escalated = set(activities.mapped("res_id"))

        for load in unacknowledged:
            if load.id in already_escalated:
                continue

            tx = load.transaction_id
            user_id = tx.user_id.id if tx and tx.user_id else self.env.user.id

            load.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user_id,
                summary=f"URGENT: No carrier acknowledgment for {load.name}",
                note=f"Carrier has not acknowledged dispatch sent {load.dispatch_sent}.",
            )

            try:
                load.action_send_dispatch_direct()
                _logger.info("Resent dispatch for load %s", load.name)
            except Exception as e:
                _logger.error("Failed to resend dispatch for load %s: %s", load.name, str(e))

        return True

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

    def action_send_dispatch_direct(self):
        """Send dispatch packet directly and track timestamp.

        Unlike action_send_dispatch_packet which opens a composer,
        this method sends immediately and sets dispatch_sent timestamp.
        """
        self.ensure_one()
        if not self.carrier_id:
            raise UserError(f"Load {self.name}: Carrier is required to send dispatch.")
        if not self.carrier_id.email:
            raise UserError(f"Carrier {self.carrier_id.name} has no email address.")

        template = self._get_email_template("email_template_dispatch_packet")
        template.send_mail(self.id, force_send=True)
        self.dispatch_sent = fields.Datetime.now()
        self.message_post(body="Dispatch packet sent to carrier.")
        return True

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

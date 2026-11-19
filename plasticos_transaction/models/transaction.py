import logging
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..dock_rule import APPOINTMENT, rule_from_site_then_company

_logger = logging.getLogger(__name__)

PRODUCT_PRICE = "Product Price"
ACCOUNT_MOVE = "account.move"
RES_PARTNER = "res.partner"
PLASTICOS_MATERIAL_PROFILE = "plasticos.material.profile"
PLASTICOS_TRANSACTION = "plasticos.transaction"
OPERATIONS_MANAGER_GROUP = "plasticos_security_base.group_operations_manager"
_REFUND_TYPES = frozenset({"out_refund", "in_refund"})
_HISTORICAL_REOPEN_ID = "plasticos_historical_reopen_id"
_HISTORICAL_REOPEN_REASON = "plasticos_historical_reopen_reason"
_MANAGER_GROUP = "plasticos_transaction.group_plasticos_manager"


def _signed_move_total(moves) -> float:
    """Invoice totals minus credit notes."""
    total = 0.0
    for move in moves:
        sign = -1.0 if move.move_type in _REFUND_TYPES else 1.0
        total += sign * (move.amount_total or 0.0)
    return total


class PlasticosTransaction(models.Model):
    _name = "plasticos.transaction"
    _description = "Plasticos Transaction"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, copy=False, default="New")

    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
        help="Responsible salesperson. Uses Odoo native user_id convention.",
        ondelete="restrict",
    )

    sale_order_id = fields.Many2one("sale.order", ondelete="restrict")
    purchase_order_ids = fields.Many2many("purchase.order")
    # Commercial archive provenance, not a payment/collection state.
    legacy_erp_history = fields.Boolean(
        string="Historical ERP Import", readonly=True, copy=False, index=True, default=False
    )
    legacy_erp_status = fields.Char(string="Source Worksheet Status", readonly=True, copy=False)

    # ── Partner References (harvested from linda_logistics_v6) ──
    supplier_id = fields.Many2one(
        RES_PARTNER,
        string="Supplier",
        domain=[("is_company", "=", True), ("supplier_rank", ">", 0)],
        tracking=True,
        index=True,
        ondelete="restrict",
    )
    buyer_id = fields.Many2one(
        RES_PARTNER,
        string="Buyer",
        domain=[("is_company", "=", True), ("customer_rank", ">", 0)],
        tracking=True,
        index=True,
        ondelete="restrict",
    )
    carrier_id = fields.Many2one(
        RES_PARTNER,
        string="Carrier",
        domain=[("is_company", "=", True)],
        tracking=True,
        ondelete="restrict",
    )

    # ── Denormalized Material Profile Links (fast lookup) ──────
    supplier_profile_id = fields.Many2one(
        PLASTICOS_MATERIAL_PROFILE,
        string="Supplier Material Profile",
        compute="_compute_profile_refs",
        store=True,
        help="Denormalized link to supplier's material profile for fast lookup.",
        ondelete="restrict",
    )
    buyer_profile_id = fields.Many2one(
        PLASTICOS_MATERIAL_PROFILE,
        string="Buyer Material Profile",
        compute="_compute_profile_refs",
        store=True,
        help="Denormalized link to buyer's material profile for fast lookup.",
        ondelete="restrict",
    )

    # Denormalized profile references (computed/stored for fast lookup)
    buyer_facility_id = fields.Many2one(
        "plasticos.facility.profile",
        string="Buyer Facility Profile",
        compute="_compute_profiles",
        store=True,
        index=True,
        help="Cached facility capability profile from sale order partner",
        ondelete="restrict",
    )

    supplier_material_id = fields.Many2one(
        PLASTICOS_MATERIAL_PROFILE,
        string="Supplier Material Profile (PO)",
        compute="_compute_profiles",
        store=True,
        index=True,
        help="Cached material profile from primary purchase order partner",
        ondelete="restrict",
    )

    # ── Product Info (harvested) ───────────────────────────────
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        tracking=True,
        ondelete="restrict",
    )
    quantity = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        tracking=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        ondelete="restrict",
    )
    unit_price = fields.Float(
        string="Unit Price",
        digits=PRODUCT_PRICE,
        tracking=True,
    )

    # ── Logistics Dates (harvested) ────────────────────────────
    expected_pickup_date = fields.Datetime(
        string="Expected Pickup Date",
        tracking=True,
    )
    actual_pickup_date = fields.Datetime(
        string="Actual Pickup Date",
        tracking=True,
    )
    expected_delivery_date = fields.Datetime(
        string="Expected Delivery Date",
        tracking=True,
    )
    actual_delivery_date = fields.Datetime(
        string="Actual Delivery Date",
        tracking=True,
    )

    # ── Logistics Terms (harvested) ────────────────────────────
    delivery_term = fields.Selection(
        [
            ("fcfs", "First Come First Served"),
            ("appointment", "Appointment Required"),
        ],
        string="Delivery Dock Rule",
        default=lambda self: self._get_default_delivery_term(),
        tracking=True,
        help=(
            "Delivery-side dock rule. Defaults from the sale order ship-to site, "
            "then that site's commercial company, then Appointment."
        ),
    )
    pickup_dock_rule = fields.Selection(
        [
            ("fcfs", "First Come First Served"),
            ("appointment", "Appointment Required"),
        ],
        string="Pickup Dock Rule",
        default=lambda self: self._get_default_pickup_dock_rule(),
        tracking=True,
        help=(
            "Pickup-side dock rule. The pickup partner is the load's pickup partner, "
            "else the purchase-order vendor's single site, else the vendor. "
            "The rule is that partner's site rule, then its commercial company, then Appointment."
        ),
    )
    freight_rate = fields.Float(
        string="Freight Rate",
        digits=PRODUCT_PRICE,
        tracking=True,
    )
    freight_actual = fields.Float(
        string="Actual Freight Cost",
        digits=PRODUCT_PRICE,
        tracking=True,
    )

    # ── Weight Tracking (harvested) ────────────────────────────
    expected_weight = fields.Float(
        string="Expected Weight (lbs)",
        tracking=True,
    )
    actual_weight = fields.Float(
        string="Actual Weight (lbs)",
        tracking=True,
    )
    weight_variance_percent = fields.Float(
        string="Weight Variance %",
        compute="_compute_weight_variance",
        store=True,
    )

    # ══════════════════════════════════════════════════════════════
    # Weight Reconciliation System
    # Priority: scale_weight > buyer_weight > supplier_weight
    # ══════════════════════════════════════════════════════════════

    # ── Weight Sources (manual entry) ─────────────────────────────
    supplier_weight = fields.Float(
        string="Supplier Weight (lbs)",
        help="Weight from supplier PO/packing list.",
        tracking=True,
    )
    buyer_weight = fields.Float(
        string="Buyer Weight (lbs)",
        help="Weight from buyer receiving report.",
        tracking=True,
    )
    scale_weight = fields.Float(
        string="Scale Weight (lbs)",
        help="Weight from 3rd party scale ticket (preferred).",
        tracking=True,
    )
    gross_weight = fields.Float(
        string="Gross Weight (lbs)",
        help="Selected gross weight before tare deduction.",
        compute="_compute_final_weight",
        store=True,
    )

    # ── Computed Final Weight ─────────────────────────────────────
    final_weight = fields.Float(
        string="Final Net Weight (lbs)",
        compute="_compute_final_weight",
        store=True,
        help="Net weight after tare deduction. Used for billing and deductions.",
    )
    weight_source = fields.Selection(
        [
            ("scale", "Scale Ticket"),
            ("buyer", "Buyer Report"),
            ("supplier", "Supplier Weight"),
            ("none", "No Weight"),
        ],
        string="Weight Source",
        compute="_compute_final_weight",
        store=True,
        help="Which weight source was used for final weight.",
    )

    # ── Tare System ───────────────────────────────────────────────
    unit_count = fields.Integer(
        string="Unit Count",
        default=0,
        help="Number of packaging units (bales, gaylords, pallets, etc.).",
    )
    unit_type = fields.Selection(
        [
            ("bale", "Bale"),
            ("gaylord", "Gaylord"),
            ("pallet", "Pallet"),
            ("box", "Box"),
            ("super_sack", "Super Sack"),
        ],
        string="Unit Type",
        help="Type of packaging unit for tare calculation.",
    )
    tare_per_unit_override = fields.Float(
        string="Tare Override (lbs)",
        help="Manual override for tare per unit. When set, takes precedence over computed value.",
    )
    tare_per_unit = fields.Float(
        string="Tare per Unit (lbs)",
        compute="_compute_tare_per_unit",
        inverse="_inverse_tare_per_unit",
        store=True,
        readonly=False,
        help="Tare weight per unit. Auto-set by unit type, but editable.",
    )
    total_tare = fields.Float(
        string="Total Tare (lbs)",
        compute="_compute_total_tare",
        store=True,
        help="Total tare weight = unit_count × tare_per_unit.",
    )

    # ── Weight Discrepancy ────────────────────────────────────────
    weight_discrepancy_pct = fields.Float(
        string="Weight Discrepancy %",
        compute="_compute_weight_discrepancy",
        store=True,
        help="Percentage difference between supplier and buyer weights.",
    )
    weight_discrepancy_flagged = fields.Boolean(
        string="Discrepancy Flagged",
        compute="_compute_weight_discrepancy",
        store=True,
        help="True if discrepancy exceeds 5%.",
    )

    # ── Light Weight Deduction ────────────────────────────────────
    minimum_net_weight = fields.Float(
        string="Minimum Net Weight (lbs)",
        help="Stated minimum net weight from PO. Used for light weight deduction.",
    )
    light_weight_deduction_rate = fields.Float(
        string="Deduction Rate ($/lb)",
        default=0.01,
        help="Deduction rate per pound below minimum. Default: $0.01/lb.",
    )
    light_weight_deduction = fields.Float(
        string="Light Weight Deduction ($)",
        compute="_compute_light_weight_deduction",
        store=True,
        help="Penalty for loading below minimum weight.",
    )
    dead_freight_chargeback = fields.Boolean(
        string="Dead Freight Chargeback",
        compute="_compute_light_weight_deduction",
        store=True,
        help="True if deduction exceeds purchase price (supplier charged for dead freight).",
    )

    # ── Quality Control ────────────────────────────────────────
    # NOTE: has_quality_claim is now a simple stored field.
    # The compute logic was moved to plasticos_claims module
    # which extends this model with claim_ids and recomputes this field.
    has_quality_claim = fields.Boolean(
        string="Has Quality Claim",
        default=False,
    )

    customer_invoice_id = fields.Many2one(ACCOUNT_MOVE, domain=[("move_type", "=", "out_invoice")], ondelete="restrict")

    vendor_bill_ids = fields.Many2many(
        ACCOUNT_MOVE, relation="plasticos_tx_vendor_rel", domain=[("move_type", "=", "in_invoice")]
    )

    freight_bill_ids = fields.Many2many(
        ACCOUNT_MOVE, relation="plasticos_tx_freight_rel", domain=[("move_type", "=", "in_invoice")]
    )

    # ── RevOps Financial Fields ──────────────────────────────
    other_expenses = fields.Float(
        string="Other Expenses",
        help="Manual field for any other direct costs not captured in bills.",
    )
    freight_chargebacks = fields.Float(
        string="Freight Chargebacks",
        help="Credits recovered from carriers (CST violations, blown double-blinds).",
    )
    lightweight_penalties = fields.Float(
        string="Lightweight Penalties",
        help="Credits recovered from suppliers for loading below minimum weight.",
    )
    # NOTE: claim_ids field moved to plasticos_claims module to avoid circular dependency
    # claim_ids = fields.One2many(
    #     "plasticos.claim",
    #     "transaction_id",
    #     string="Claims",
    #     help="QC cases, chargebacks, and penalty claims linked to this transaction.",
    # )

    # Historical line items from legacy ERP import
    line_ids = fields.One2many(
        "plasticos.transaction.line",
        "transaction_id",
        string="Transaction Lines",
    )
    line_count = fields.Integer(
        compute="_compute_line_count",
        store=True,
    )

    # Historical totals (from imported data, separate from computed financials)
    historical_sale_total = fields.Float(
        string="Historical Sale Total",
        compute="_compute_historical_totals",
        store=True,
    )
    historical_purchase_total = fields.Float(
        string="Historical Purchase Total",
        compute="_compute_historical_totals",
        store=True,
    )
    historical_margin = fields.Float(
        string="Historical Margin",
        compute="_compute_historical_totals",
        store=True,
    )

    # ── Computed Financial Totals ──────────────────────────────
    revenue_total = fields.Float(
        string="Revenue Total",
        compute="_compute_financials",
        store=True,
        help="Total from customer invoice(s).",
    )
    purchase_cost_total = fields.Float(
        string="Purchase Cost",
        compute="_compute_financials",
        store=True,
        help="Total from vendor bill(s).",
    )
    freight_cost_total = fields.Float(
        string="Freight Cost",
        compute="_compute_financials",
        store=True,
        help="Total from carrier bill(s).",
    )
    cost_total = fields.Float(
        string="Total Cost",
        compute="_compute_financials",
        store=True,
        help="Sum of purchase + freight + other expenses.",
    )
    gross_margin = fields.Float(
        string="Gross Margin",
        compute="_compute_financials",
        store=True,
        help="Revenue - costs + chargebacks + penalties (pre-commission).",
    )
    net_margin = fields.Float(
        string="Net Margin",
        compute="_compute_net_margin",
        store=True,
        help="Gross margin - commission (company profit).",
    )

    # Commission fields (commission_rule_id, commission_locked, commission_locked_amount,
    # commission_override_pct) are defined by plasticos_commission via _inherit extension
    # (transaction_commission.py) to avoid circular dependency.
    # commission_amount is kept here as a stub so _compute_net_margin works without
    # requiring the commission module.
    commission_amount = fields.Float(
        compute="_compute_commission",
        store=True,
        help="Computed by plasticos_commission extension. Zero when commission not installed.",
    )

    compliance_status = fields.Selection(
        [("compliant", "Compliant"), ("missing", "Missing Docs")],
        compute="_compute_compliance",
        store=True,
        index=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("pending_supplier", "Pending Supplier"),
            ("supplier_not_ready", "Supplier Not Ready"),
            ("supplier_ready", "Supplier Ready"),
            ("do_created", "DO Created"),
            ("dispatched", "Dispatched"),
            ("in_progress", "In Progress"),
            ("in_transit", "In Transit"),
            ("delivered", "Delivered"),
            ("invoiced", "Invoiced"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
        index=True,
    )

    # ── Supplier Confirmation Tracking ────────────────────────
    supplier_confirmation_sent = fields.Datetime(
        string="Confirmation Sent",
        tracking=True,
        help="When supplier was asked to confirm readiness.",
    )
    supplier_confirmation_received = fields.Datetime(
        string="Confirmation Received",
        tracking=True,
        help="When supplier confirmed they are ready.",
    )
    is_supplier_confirmed = fields.Boolean(
        string="Supplier Confirmed",
        compute="_compute_is_supplier_confirmed",
        store=True,
        help="True when supplier has confirmed readiness. Distinct from 'supplier_ready' state.",
    )
    supplier_confirmation_followup_count = fields.Integer(
        string="Followup Count",
        default=0,
        help="Number of follow-up emails sent for supplier confirmation.",
    )
    last_supplier_confirmation_followup_on = fields.Datetime(
        string="Last Followup",
        help="When the last follow-up was sent.",
    )
    supplier_not_ready_reason = fields.Text(
        string="Not Ready Reason",
        help="Reason provided when supplier indicated they are not ready.",
    )

    # ── Delivery Order (PO-to-DO Workflow) ────────────────────
    delivery_order_id = fields.Many2one(
        "stock.picking",
        string="Delivery Order",
        domain=[("picking_type_code", "=", "outgoing")],
        tracking=True,
        help="Linked delivery order for this transaction.",
        ondelete="restrict",
    )
    do_number = fields.Char(
        string="DO Number",
        related="delivery_order_id.name",
        store=True,
        help="Delivery order reference number.",
    )

    # ── Constraints ──────────────────────────────────────────
    _unique_name = models.Constraint(
        "unique(name)",
        "Transaction reference must be unique.",
    )

    def _check_override_pct_range(self):
        """Stub — overridden by plasticos_commission.transaction_commission.

        The range check lives on that inherit, which owns commission_override_pct.
        """

    # ── Dock rules (ADR-135 §3) ──────────────────────────────
    def _get_default_delivery_term(self):
        """Delivery rule for a form default. Create fills the value from the sale order."""
        sale_id = self.env.context.get("default_sale_order_id")
        if not sale_id:
            return APPOINTMENT
        sale = self.env["sale.order"].browse(sale_id)
        return self._dock_rule_for_partner(sale.partner_shipping_id or sale.partner_id)

    def _get_default_pickup_dock_rule(self):
        """Pickup rule for a form default. Create fills the value from the vendor or context."""
        partner_id = self.env.context.get("default_pickup_partner_id")
        if not partner_id:
            return APPOINTMENT
        return self._dock_rule_for_partner(self.env[RES_PARTNER].browse(partner_id))

    def _partner_is_site(self, partner) -> bool:
        if not partner:
            return False
        return bool(partner._plasticos_is_site())

    def _dock_rule_for_partner(self, partner) -> str:
        """Site rule, else the commercial company's rule, else Appointment."""
        if not partner:
            return APPOINTMENT
        commercial = partner.commercial_partner_id or partner
        is_site = self._partner_is_site(partner)
        return rule_from_site_then_company(
            partner.default_delivery_term if is_site else None,
            commercial.default_delivery_term,
            partner_is_site=is_site,
        )

    def _vendor_or_its_single_site(self, vendor):
        """The vendor when it is a site, else its only site, else the vendor itself."""
        if not vendor:
            return vendor
        if self._partner_is_site(vendor):
            return vendor
        commercial = vendor.commercial_partner_id or vendor
        sites = commercial.child_ids.filtered(lambda child: self._partner_is_site(child))
        if len(sites) == 1:
            return sites
        return vendor

    def _pickup_partners_from_loads(self):
        """Pickup partners named on this transaction's loads. Logistics owns the loads."""
        return self.env["res.partner"]

    def _resolved_pickup_partner(self):
        """Load pickup partner, else the PO vendor's single site, else the PO vendor.

        A saved transaction consults its loads. Create has no loads yet, so it
        uses ``default_pickup_partner_id`` or the vendor named in the values.
        Several loads that name different pickup partners fall through to the vendor.
        """
        self.ensure_one()
        pickups = self._pickup_partners_from_loads()
        if len(pickups) == 1:
            return pickups
        vendor = self.purchase_order_ids[:1].partner_id or self.supplier_id
        return self._vendor_or_its_single_site(vendor)

    def _vendor_from_po_commands(self, commands):
        ids: list[int] = []
        for command in commands or []:
            if not isinstance(command, (list, tuple)) or not command:
                continue
            kind = command[0]
            if kind == Command.SET and len(command) >= 3:
                ids.extend(command[2] or [])
            elif kind == Command.LINK and len(command) >= 2:
                ids.append(command[1])
        if not ids:
            return self.env[RES_PARTNER]
        return self.env["purchase.order"].browse(ids[0]).partner_id

    def _fill_dock_rule_vals(self, vals):
        """Set either side only when the caller did not pass it."""
        if "delivery_term" not in vals:
            sale = self.env["sale.order"].browse(vals["sale_order_id"]) if vals.get("sale_order_id") else False
            partner = (sale.partner_shipping_id or sale.partner_id) if sale else self.env[RES_PARTNER]
            vals["delivery_term"] = self._dock_rule_for_partner(partner)
        if "pickup_dock_rule" not in vals:
            context_partner = self.env.context.get("default_pickup_partner_id")
            if context_partner:
                partner = self.env[RES_PARTNER].browse(context_partner)
            else:
                vendor = self._vendor_from_po_commands(vals.get("purchase_order_ids"))
                if not vendor and vals.get("supplier_id"):
                    vendor = self.env[RES_PARTNER].browse(vals["supplier_id"])
                partner = self._vendor_or_its_single_site(vendor)
            vals["pickup_dock_rule"] = self._dock_rule_for_partner(partner)

    @api.onchange("sale_order_id")
    def _onchange_delivery_dock_rule(self):
        for record in self:
            sale = record.sale_order_id
            partner = (sale.partner_shipping_id or sale.partner_id) if sale else self.env[RES_PARTNER]
            record.delivery_term = record._dock_rule_for_partner(partner)

    @api.onchange("supplier_id", "purchase_order_ids")
    def _onchange_pickup_dock_rule(self):
        for record in self:
            record.pickup_dock_rule = record._dock_rule_for_partner(record._resolved_pickup_partner())

    # ── Supplier Confirmation Compute ────────────────────────
    @api.depends("supplier_confirmation_received")
    def _compute_is_supplier_confirmed(self):
        for record in self:
            record.is_supplier_confirmed = bool(record.supplier_confirmation_received)

    # ── Computed Methods (harvested) ──────────────────────────
    @api.depends(
        "supplier_id",
        "supplier_id.material_profile_ids",
        "supplier_id.material_profile_ids.form_id",
        "buyer_id",
        "buyer_id.material_profile_ids",
        "buyer_id.material_profile_ids.form_id",
        "product_id",
        "product_id.product_tmpl_id.polymer_id",
    )
    def _compute_profile_refs(self):
        """Denormalize material profile links for fast lookup.

        Matches supplier/buyer to their material profile based on the
        transaction's product polymer. One search covers the recordset.
        When several profiles share a partner and polymer and at least one
        has a form, the first form-specified row in model order is kept and
        form-unspecified rows are ignored. When every match has an empty
        form, that unspecified profile is selected.

        Note: product.template has polymer_id (via plasticos_product) but not
        form_id. We match on polymer only; form matching requires order line fields.
        """
        Profile = self.env[PLASTICOS_MATERIAL_PROFILE]
        polymer_by_tx = {}
        partner_ids = set()
        polymer_ids = set()
        for rec in self:
            tmpl = rec.product_id.product_tmpl_id if rec.product_id else False
            polymer = tmpl.polymer_id if tmpl and getattr(tmpl, "polymer_id", False) else False
            polymer_by_tx[rec.id] = polymer.id if polymer else False
            if not polymer:
                continue
            polymer_ids.add(polymer.id)
            if rec.supplier_id:
                partner_ids.add(rec.supplier_id.id)
            if rec.buyer_id:
                partner_ids.add(rec.buyer_id.id)
        first_match = {}
        if partner_ids and polymer_ids:
            profiles = Profile.search(
                [
                    ("partner_id", "in", list(partner_ids)),
                    ("polymer_id", "in", list(polymer_ids)),
                ]
            )
            grouped = {}
            for profile in profiles:
                grouped.setdefault((profile.partner_id.id, profile.polymer_id.id), []).append(profile)
            for key, rows in grouped.items():
                specified = [row for row in rows if row.form_id]
                first_match[key] = specified[0] if specified else rows[0]
        for rec in self:
            polymer_id = polymer_by_tx[rec.id]
            supplier_key = (rec.supplier_id.id, polymer_id) if polymer_id and rec.supplier_id else None
            buyer_key = (rec.buyer_id.id, polymer_id) if polymer_id and rec.buyer_id else None
            rec.supplier_profile_id = first_match.get(supplier_key, False) if supplier_key else False
            rec.buyer_profile_id = first_match.get(buyer_key, False) if buyer_key else False

    @api.depends(
        "sale_order_id",
        "sale_order_id.partner_id",
        "sale_order_id.partner_id.facility_profile_ids",
        "purchase_order_ids",
        "purchase_order_ids.partner_id",
        "purchase_order_ids.partner_id.material_profile_ids",
    )
    def _compute_profiles(self):
        """Buyer facility is the sale-order partner's facility profile.

        Supplier material stays the first material profile of the first
        purchase-order partner, in material-profile order. Facility uniqueness
        is already ``unique(partner_id)``, so the partner's existing one2many
        is the authoritative row.
        """
        Profile = self.env[PLASTICOS_MATERIAL_PROFILE]
        partner_ids = set()
        for rec in self:
            first_po = rec.purchase_order_ids[:1]
            if first_po.partner_id:
                partner_ids.add(first_po.partner_id.id)
        first_material = {}
        if partner_ids:
            for profile in Profile.search([("partner_id", "in", list(partner_ids))]):
                first_material.setdefault(profile.partner_id.id, profile)
        empty_partner = self.env[RES_PARTNER]
        for rec in self:
            buyer = rec.sale_order_id.partner_id if rec.sale_order_id else empty_partner
            rec.buyer_facility_id = buyer.facility_profile_ids[:1]
            first_po = rec.purchase_order_ids[:1]
            if first_po.partner_id:
                rec.supplier_material_id = first_material.get(first_po.partner_id.id, False)
            else:
                rec.supplier_material_id = False

    @api.depends("expected_weight", "actual_weight")
    def _compute_weight_variance(self):
        for rec in self:
            if rec.expected_weight and rec.actual_weight:
                rec.weight_variance_percent = abs(rec.actual_weight - rec.expected_weight) / rec.expected_weight * 100
            else:
                rec.weight_variance_percent = 0.0

    # ══════════════════════════════════════════════════════════════
    # Weight Reconciliation Computed Methods
    # ══════════════════════════════════════════════════════════════

    @api.depends("unit_type", "tare_per_unit_override")
    def _compute_tare_per_unit(self):
        """Set default tare weight based on unit type.

        If tare_per_unit_override is set, use that value instead of the default.

        Defaults:
        - bale: 0 lbs (no tare)
        - gaylord: 40 lbs
        - pallet: 40 lbs
        - box: 0 lbs
        - super_sack: 0 lbs
        """
        tare_defaults = {
            "bale": 0.0,
            "gaylord": 40.0,
            "pallet": 40.0,
            "box": 0.0,
            "super_sack": 0.0,
        }
        for rec in self:
            if rec.tare_per_unit_override:
                rec.tare_per_unit = rec.tare_per_unit_override
            elif rec.unit_type:
                rec.tare_per_unit = tare_defaults.get(rec.unit_type, 0.0)
            else:
                rec.tare_per_unit = 0.0

    def _inverse_tare_per_unit(self):
        """Store user-edited tare value in the override field."""
        for rec in self:
            rec.tare_per_unit_override = rec.tare_per_unit

    @api.depends("unit_count", "tare_per_unit")
    def _compute_total_tare(self):
        """Calculate total tare = unit_count × tare_per_unit."""
        for rec in self:
            rec.total_tare = (rec.unit_count or 0) * (rec.tare_per_unit or 0.0)

    @api.depends("scale_weight", "buyer_weight", "supplier_weight", "total_tare")
    def _compute_final_weight(self):
        """Compute final net weight using priority: scale > buyer > supplier.

        gross_weight = selected source weight
        final_weight = gross_weight - total_tare (never negative)
        """
        for rec in self:
            # Priority selection
            if rec.scale_weight and rec.scale_weight > 0:
                gross = rec.scale_weight
                source = "scale"
            elif rec.buyer_weight and rec.buyer_weight > 0:
                gross = rec.buyer_weight
                source = "buyer"
            elif rec.supplier_weight and rec.supplier_weight > 0:
                gross = rec.supplier_weight
                source = "supplier"
            else:
                gross = 0.0
                source = "none"

            rec.gross_weight = gross
            rec.weight_source = source
            # Net weight = gross - tare, never negative
            rec.final_weight = max(gross - (rec.total_tare or 0.0), 0.0)

    @api.depends("supplier_weight", "buyer_weight")
    def _compute_weight_discrepancy(self):
        """Flag discrepancy if supplier vs buyer weight differs by >5%.

        Only computes when both weights are present and positive.
        Protects against divide-by-zero.
        """
        for rec in self:
            sw = rec.supplier_weight or 0.0
            bw = rec.buyer_weight or 0.0

            if sw > 0 and bw > 0:
                max_weight = max(sw, bw)
                discrepancy = abs(sw - bw) / max_weight
                rec.weight_discrepancy_pct = discrepancy * 100  # Store as percentage
                rec.weight_discrepancy_flagged = discrepancy > 0.05
            else:
                rec.weight_discrepancy_pct = 0.0
                rec.weight_discrepancy_flagged = False

    @api.depends("final_weight", "minimum_net_weight", "light_weight_deduction_rate", "purchase_cost_total")
    def _compute_light_weight_deduction(self):
        """Calculate light weight penalty if final_weight < minimum_net_weight.

        Deduction = (minimum - actual) × rate
        If deduction > purchase_cost_total → dead_freight_chargeback = True
        """
        for rec in self:
            min_weight = rec.minimum_net_weight or 0.0
            actual = rec.final_weight or 0.0
            rate = rec.light_weight_deduction_rate or 0.01
            purchase_cost = rec.purchase_cost_total or 0.0

            if min_weight > 0 and actual < min_weight:
                shortfall = min_weight - actual
                deduction = shortfall * rate
                rec.light_weight_deduction = deduction
                rec.dead_freight_chargeback = deduction > purchase_cost if purchase_cost > 0 else False
            else:
                rec.light_weight_deduction = 0.0
                rec.dead_freight_chargeback = False

    # NOTE: _compute_has_quality_claim moved to plasticos_claims module
    # which extends plasticos.transaction with claim_ids field

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends("line_ids.sale_amount", "line_ids.purchase_amount")
    def _compute_historical_totals(self):
        for rec in self:
            rec.historical_sale_total = sum(rec.line_ids.mapped("sale_amount"))
            rec.historical_purchase_total = sum(rec.line_ids.mapped("purchase_amount"))
            rec.historical_margin = rec.historical_sale_total - rec.historical_purchase_total

    @api.depends(
        "customer_invoice_id",
        "customer_invoice_id.amount_total",
        "customer_invoice_id.reversal_move_ids",
        "customer_invoice_id.reversal_move_ids.amount_total",
        "customer_invoice_id.reversal_move_ids.state",
        "customer_invoice_id.debit_note_ids",
        "customer_invoice_id.debit_note_ids.amount_total",
        "customer_invoice_id.debit_note_ids.state",
        "vendor_bill_ids",
        "vendor_bill_ids.amount_total",
        "freight_bill_ids",
        "freight_bill_ids.amount_total",
        "freight_actual",
        "other_expenses",
        "freight_chargebacks",
        "lightweight_penalties",
    )
    def _compute_financials(self):
        """RevOps formula: gross_margin = revenue - costs + recoveries.

        Revenue is the customer document set of the transaction, each document
        once: the customer invoice, plus the debit notes raised on it
        (``debit_origin_id``), minus the credit notes that reverse it
        (``reversed_entry_id``). Each document carries exactly one of those
        links, so nothing is counted or netted twice.
        """
        for rec in self:
            invoice = rec.customer_invoice_id
            live = lambda move: move.state != "cancel"  # noqa: E731 - one predicate for both document sets
            credit_notes = invoice.reversal_move_ids.filtered(live)
            debit_notes = invoice.debit_note_ids.filtered(live)
            revenue = _signed_move_total(invoice) + _signed_move_total(credit_notes) + _signed_move_total(debit_notes)
            purchase_cost = _signed_move_total(rec.vendor_bill_ids)
            billed_freight = _signed_move_total(rec.freight_bill_ids)
            freight_cost = billed_freight or (rec.freight_actual or 0.0)
            other = rec.other_expenses or 0.0

            # Recoveries reduce effective cost
            chargebacks = rec.freight_chargebacks or 0.0
            penalties = rec.lightweight_penalties or 0.0

            total_cost = purchase_cost + freight_cost + other
            gross = revenue - total_cost + chargebacks + penalties

            rec.revenue_total = revenue
            rec.purchase_cost_total = purchase_cost
            rec.freight_cost_total = freight_cost
            rec.cost_total = total_cost
            rec.gross_margin = gross

    @api.depends("gross_margin", "commission_amount")
    def _compute_net_margin(self):
        """Net margin = gross margin - commission. Overridden by plasticos_commission."""
        for rec in self:
            rec.net_margin = rec.gross_margin - (rec.commission_amount or 0.0)

    @api.depends()
    def _compute_chargebacks_penalties(self):
        """Fallback: zero chargebacks/penalties when claims module not installed.

        NOTE: When plasticos_claims is installed, this method is overridden by
        transaction_claims.py which uses @api.depends("claim_ids", ...) for
        automatic updates when claims are resolved.
        """
        for rec in self:
            rec.freight_chargebacks = 0.0
            rec.lightweight_penalties = 0.0

    @api.depends()
    def _compute_commission(self):
        """Stub — overridden by plasticos_commission.transaction_commission.
        Falls back to zero when commission module is not installed.
        """
        for rec in self:
            rec.commission_amount = 0.0

    @api.depends("create_date")
    def _compute_compliance(self):
        """Default when Documents is absent. The documents bridge owns the service.

        Observational only. Document transitions must not post invoices, bills,
        or freight bills. Explicit Accounting ``action_post`` remains the posting
        command.
        """
        for rec in self:
            rec.compliance_status = "compliant"

    def _missing_close_documents(self, rec):
        """Documents addon blocks close when required files are missing."""
        return False

    def _reconcile_new_transaction_loads(self, records):
        return

    def _lock_loads_for_party_write(self, vals):
        return

    def _refuse_loaded_sale_reassignment(self, vals):
        return

    def _reconcile_loads_after_party_write(self, vals):
        return

    def _refuse_unlink_with_loads(self, rec):
        return

    def _auto_post_pending_invoices(self):
        """Post draft invoices/bills when an explicit caller asks.

        Compliance recompute does not call this. Historical ERP drafts,
        identified by their ir.model.data marker, stay draft.

        Posts: customer_invoice_id, vendor_bill_ids, freight_bill_ids.
        Only posts moves in 'draft' state to avoid double-posting.
        Historical ERP drafts, identified by their ir.model.data marker, stay
        draft for an explicit accounting post.
        """
        self.ensure_one()
        moves_to_post = self.env[ACCOUNT_MOVE]

        if self.customer_invoice_id and self.customer_invoice_id.state == "draft":
            moves_to_post |= self.customer_invoice_id

        for bill in self.vendor_bill_ids.filtered(lambda m: m.state == "draft"):
            moves_to_post |= bill

        for bill in self.freight_bill_ids.filtered(lambda m: m.state == "draft"):
            moves_to_post |= bill

        moves_to_post -= self._historical_erp_moves(moves_to_post)
        if moves_to_post:
            moves_to_post.action_post()

    @api.model
    def _historical_erp_moves(self, moves):
        """Moves whose identity is an imported historical account.move.

        Same classifier as account.move._historical_source_ids. Compliance
        recompute does not call _auto_post_pending_invoices.
        """
        if not moves:
            return moves
        return moves.browse(list(moves._historical_source_ids()))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(PLASTICOS_TRANSACTION) or "New"
            self._fill_dock_rule_vals(vals)
        names = [vals.get("name") for vals in vals_list if vals.get("name") and vals.get("name") != "New"]
        existing_names = set(self.search([("name", "in", names)]).mapped("name")) if names else set()
        for name in names:
            if name in existing_names:
                raise ValidationError(f"Transaction reference '{name}' already exists.")
        records = super().create(vals_list)
        linked = records.filtered("purchase_order_ids")
        if linked:
            linked.purchase_order_ids._compute_pickup_dock_rule_from_transaction()
        self._reconcile_new_transaction_loads(records)
        return records

    def write(self, vals):
        name = vals.get("name")
        if name and self:
            holders = self.search([("name", "=", name)])
            for record in self:
                if holders - record:
                    raise ValidationError(f"Transaction reference '{name}' already exists.")
        self._lock_loads_for_party_write(vals)
        bill_owners = self._bill_owners_for_write(vals)
        for rec in self:
            self._validate_state_transition(rec, vals)
            self._validate_write_immutability(rec, vals)
            self._validate_bill_uniqueness(rec, bill_owners)
        self._refuse_loaded_sale_reassignment(vals)
        reopened = self.filtered(lambda rec: self._authorized_historical_reopen(rec, vals))
        res = super().write(vals)
        if reopened:
            self._post_historical_reopen(reopened)
        if {"pickup_dock_rule", "purchase_order_ids"} & set(vals) and self.purchase_order_ids:
            self.purchase_order_ids._compute_pickup_dock_rule_from_transaction()
        self._reconcile_loads_after_party_write(vals)
        return res

    def _validate_state_transition(self, rec, vals):
        """Enforce that state changes only happen via dedicated action methods.

        System processes (crons, automated workflows) can bypass this guard by
        setting context key 'bypass_state_guard' to True.

        INTERNAL ONLY — never expose 'bypass_state_guard' in XML button context attrs.
        This key is reserved for:
        - action_mark_* methods in this model
        - Cron jobs that need to update state programmatically
        - Automated workflow rules (base.automation)

        Direct write() calls from UI or external API should NEVER use this key.
        """
        if "state" in vals:
            if self.env.context.get("bypass_state_guard"):
                return

            allow = vals.get("state") == "active" or (
                vals.get("state") == "closed" and vals.get("commission_locked") is True
            )
            if not allow:
                raise UserError("State can only be changed via action methods.")

    def _validate_write_immutability(self, rec, vals):
        """Guard immutable fields: name, closed-state fields, invoice reassignment.
        Commission-specific guards (commission_rule_id, commission_locked) are
        enforced by plasticos_commission.transaction_commission.
        """
        if rec.legacy_erp_history and ({"legacy_erp_history", "legacy_erp_status"} & vals.keys()):
            raise UserError("Historical source identity and status are immutable.")
        if rec.legacy_erp_history and "state" in vals and vals["state"] != rec.state:
            if not self._authorized_historical_reopen(rec, vals):
                raise UserError("Historical trade changes require a separately approved operations migration.")
        if "name" in vals:
            raise UserError("Transaction reference cannot be modified.")
        if rec.state == "closed":
            protected = {
                "sale_order_id",
                "purchase_order_ids",
                "customer_invoice_id",
                "vendor_bill_ids",
                "freight_bill_ids",
            }
            touched = protected.intersection(vals.keys())
            if touched == {"purchase_order_ids"} and self._import_purchase_links_only(vals):
                touched = set()
            if touched:
                raise UserError("Closed transactions are immutable.")
        if rec.customer_invoice_id and "customer_invoice_id" in vals:
            if vals["customer_invoice_id"] != rec.customer_invoice_id.id:
                raise UserError("Customer invoice cannot be reassigned once set.")

    def _import_purchase_links_only(self, vals) -> bool:
        """A historical replay may attach purchase orders it did not have. It may not replace them."""
        if not self.env.context.get("import_mode"):
            return False
        commands = vals.get("purchase_order_ids") or []
        return bool(commands) and all(
            isinstance(command, (list, tuple)) and command and command[0] == Command.LINK for command in commands
        )

    def _linked_bill_ids(self, vals, field):
        if field not in vals:
            return []
        bill_ids = []
        for cmd in vals[field]:
            if cmd[0] == 4:
                bill_ids.append(cmd[1])
            elif cmd[0] == 6:
                bill_ids.extend(cmd[2])
        return bill_ids

    def _bill_owner_links(self, field, bill_ids):
        if not bill_ids:
            return {}
        taken = self.search([(field, "in", bill_ids)])
        taken[field]
        return {owner.id: set(owner[field].ids) for owner in taken}

    def _bill_owners_for_write(self, vals):
        """One search per bill field for the whole recordset, before the write loop."""
        owners = {}
        vendor_ids = self._linked_bill_ids(vals, "vendor_bill_ids")
        if vendor_ids:
            owners["vendor_bill_ids"] = (
                "Vendor bill",
                vendor_ids,
                self._bill_owner_links("vendor_bill_ids", vendor_ids),
            )
        freight_ids = self._linked_bill_ids(vals, "freight_bill_ids")
        if freight_ids:
            owners["freight_bill_ids"] = (
                "Freight bill",
                freight_ids,
                self._bill_owner_links("freight_bill_ids", freight_ids),
            )
        return owners

    def _validate_bill_uniqueness(self, rec, bill_owners):
        """Ensure each bill in M2M commands is not already linked to another transaction."""
        for label, bill_ids, links in bill_owners.values():
            linked = set()
            for owner_id, owner_bills in links.items():
                if owner_id != rec.id:
                    linked.update(owner_bills)
            for bill_id in bill_ids:
                if bill_id in linked:
                    raise UserError(f"{label} already linked to another transaction.")

    def unlink(self):
        for rec in self:
            if rec.customer_invoice_id or rec.vendor_bill_ids or rec.freight_bill_ids:
                raise UserError("Cannot delete transaction linked to accounting records.")
            if rec.state == "closed":
                raise UserError("Closed transactions cannot be deleted.")
            self._refuse_unlink_with_loads(rec)
        return super().unlink()

    def _authorized_historical_reopen(self, rec, vals):
        """Closed historical -> Active, one record, manager, reason, state only.

        The context keys are not sufficient on their own. A caller who forges
        them still fails unless the record, group, transition, and field set match.
        ``bypass_state_guard`` does not authorize this transition.
        """
        if set(vals) != {"state"} or vals.get("state") != "active":
            return False
        if rec.state != "closed" or not rec.legacy_erp_history:
            return False
        if self.env.context.get(_HISTORICAL_REOPEN_ID) != rec.id:
            return False
        if not (self.env.context.get(_HISTORICAL_REOPEN_REASON) or "").strip():
            return False
        return self.env.user.has_group(_MANAGER_GROUP)

    def _post_historical_reopen(self, records):
        reason = (self.env.context.get(_HISTORICAL_REOPEN_REASON) or "").strip()
        when = fields.Datetime.now()
        actor = self.env.user
        body = (
            f"Historical reopen by {actor.name} (user {actor.id}) at {when} UTC. "
            "State changed from Closed to Active. "
            f"Reason: {reason}"
        )
        for rec in records:
            rec.message_post(
                body=f"{body} Transaction {rec.name} (id {rec.id}).",
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def action_reopen_historical(self, reason):
        """Reopen one Closed imported transaction to Active. Replay will not close it again."""
        if len(self) != 1:
            raise UserError("Reopen one historical transaction at a time.")
        reason = (reason or "").strip()
        if not reason:
            raise UserError("A reopen reason is required.")
        rec = self
        if not rec.legacy_erp_history:
            raise UserError("Only an imported historical transaction can be reopened.")
        if rec.state != "closed":
            raise UserError("Only a Closed historical transaction can be reopened.")
        if not self.env.user.has_group(_MANAGER_GROUP):
            raise UserError("Only Plasticos Managers can reopen a historical transaction.")
        status = rec.legacy_erp_status
        invoice = rec.customer_invoice_id
        rec.with_context(
            **{
                _HISTORICAL_REOPEN_ID: rec.id,
                _HISTORICAL_REOPEN_REASON: reason,
            }
        ).write({"state": "active"})
        if rec.legacy_erp_status != status or rec.customer_invoice_id != invoice or not rec.legacy_erp_history:
            raise UserError("Historical reopen changed source identity.")
        return True

    def action_open_historical_reopen(self):
        """Open the reason wizard for the one selected historical transaction."""
        if len(self) != 1:
            raise UserError("Reopen one historical transaction at a time.")
        if not self.legacy_erp_history or self.state != "closed":
            raise UserError("Only a Closed historical transaction can be reopened.")
        if not self.env.user.has_group(_MANAGER_GROUP):
            raise UserError("Only Plasticos Managers can reopen a historical transaction.")
        return {
            "type": "ir.actions.act_window",
            "name": "Reopen Historical Transaction",
            "res_model": "plasticos.transaction.reopen.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_transaction_id": self.id},
        }

    def action_activate(self):
        """Activate a draft transaction."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(f"Cannot activate transaction: must be in 'Draft' state (current: {rec.state}).")
            rec.state = "active"

    def action_close(self):
        for rec in self:
            self._validate_close_preconditions(rec)

            self.env.cr.execute(
                "SELECT pg_try_advisory_lock(hashtext(%s))",
                [f"plasticos_transaction.close_{rec.id}"],
            )
            locked = self.env.cr.fetchone()[0]
            if not locked:
                raise UserError(f"Transaction {rec.name} is already being closed by another process.")
            try:
                self._apply_close(rec)
            finally:
                self.env.cr.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s))",
                    [f"plasticos_transaction.close_{rec.id}"],
                )

    def _lock_load_membership_for_milestone(self, rec):
        """Logistics overrides this. Base transactions have no loads."""
        return

    def _refuse_lagging_loads(self, rec, milestone, message):
        """Logistics overrides this. A transaction with no loads keeps its workflow."""
        return

    def _validate_close_preconditions(self, rec):
        """Guard all business rules that must pass before a transaction can be closed.

        Permission is checked before the membership lock so an unauthorized user
        does not hold the transaction row.
        """
        # Permission check first
        if not self.env.user.has_group("plasticos_transaction.group_plasticos_manager"):
            raise UserError("Only Plasticos Managers can close transactions.")
        self._lock_load_membership_for_milestone(rec)
        if rec.state == "closed":
            raise UserError("Transaction is already closed.")
        if not rec.customer_invoice_id or rec.customer_invoice_id.state != "posted":
            raise UserError("Customer invoice must be posted.")
        if any(bill.state != "posted" for bill in rec.vendor_bill_ids):
            raise UserError("Vendor bills must be posted.")
        self._refuse_lagging_loads(rec, "closed", "Logistics must be closed.")
        if self._missing_close_documents(rec):
            raise UserError("Required documents missing.")
        if rec.gross_margin < 0:
            raise UserError("Cannot close transaction with negative gross margin.")

    def _apply_close(self, rec):
        """Write closed state. Commission locking is applied by plasticos_commission extension."""
        rec.with_context(bypass_state_guard=True).write({"state": "closed"})

    # ═════════════════════════════════════════════════════════
    # State Transition Action Methods (for crons/system processes)
    # ═════════════════════════════════════════════════════════

    def action_mark_do_created(self):
        """Mark transaction as having a delivery order created.

        Called by cron or system process after DO is linked.
        Uses bypass_state_guard context to allow state transition.
        """
        for rec in self:
            if rec.state != "supplier_ready":
                raise UserError(
                    f"Cannot mark DO created: transaction must be in 'Supplier Ready' state (current: {rec.state})."
                )
            if not rec.delivery_order_id:
                raise UserError("Cannot mark DO created: no delivery order linked.")
            rec.with_context(bypass_state_guard=True).write({"state": "do_created"})

    def action_mark_dispatched(self):
        """Mark transaction as dispatched (load sent to carrier).

        Called when the linked load transitions to dispatched state.
        Uses bypass_state_guard context to allow state transition.
        """
        for rec in self:
            self._lock_load_membership_for_milestone(rec)
            if rec.state not in ("do_created", "supplier_ready"):
                raise UserError(
                    f"Cannot mark dispatched: transaction must be in 'DO Created' or "
                    f"'Supplier Ready' state (current: {rec.state})."
                )
            self._refuse_lagging_loads(
                rec,
                "dispatched",
                "Cannot mark dispatched: a load has not been dispatched yet.",
            )
            rec.with_context(bypass_state_guard=True).write({"state": "dispatched"})

    def action_mark_in_transit(self):
        """Mark transaction as in transit (carrier picked up load).

        Called when the linked load transitions to picked_up state.
        Uses bypass_state_guard context to allow state transition.
        """
        for rec in self:
            self._lock_load_membership_for_milestone(rec)
            if rec.state not in ("dispatched", "do_created", "in_progress"):
                raise UserError(f"Cannot mark in transit: invalid current state (current: {rec.state}).")
            self._refuse_lagging_loads(
                rec,
                "in_transit",
                "Cannot mark in transit: a load has not been picked up yet.",
            )
            rec.with_context(bypass_state_guard=True).write({"state": "in_transit"})

    def action_mark_delivered(self):
        """Mark transaction as delivered.

        Called when the linked load transitions to delivered state.
        Uses bypass_state_guard context to allow state transition.
        """
        for rec in self:
            self._lock_load_membership_for_milestone(rec)
            if rec.state != "in_transit":
                raise UserError(
                    f"Cannot mark delivered: transaction must be in 'In Transit' state (current: {rec.state})."
                )
            self._refuse_lagging_loads(
                rec,
                "delivered",
                "Cannot mark delivered: a load has not been delivered yet.",
            )
            rec.with_context(bypass_state_guard=True).write({"state": "delivered"})

    def action_mark_supplier_not_ready(self, reason=None):
        """Mark supplier as not ready with reason tracking.

        Called when supplier explicitly indicates they cannot fulfill the order
        on the expected timeline. Creates escalation activity.
        """
        for rec in self:
            if rec.state not in ("pending_supplier", "active"):
                raise UserError(
                    f"Cannot mark supplier not ready: transaction must be in "
                    f"'Pending Supplier' or 'Active' state (current: {rec.state})."
                )

            vals = {"state": "supplier_not_ready"}
            if reason:
                vals["supplier_not_ready_reason"] = reason

            rec.with_context(bypass_state_guard=True).write(vals)

            if reason:
                rec.message_post(body=f"Supplier not ready: {reason}")
            else:
                rec.message_post(body="Supplier marked as not ready.")

            rec._escalate_supplier_confirmation()

    def action_mark_supplier_ready(self):
        """Mark supplier as ready (can recover from supplier_not_ready state)."""
        for rec in self:
            if rec.state not in ("pending_supplier", "supplier_not_ready", "active"):
                raise UserError(f"Cannot mark supplier ready: invalid current state (current: {rec.state}).")

            rec.supplier_confirmation_received = fields.Datetime.now()
            rec.with_context(bypass_state_guard=True).write({"state": "supplier_ready"})
            rec.message_post(body="Supplier confirmed ready.")

    def action_send_supplier_confirmation(self):
        """Send supplier confirmation request email."""
        self.ensure_one()
        if not self.supplier_id:
            raise UserError("Cannot send confirmation: no supplier assigned.")
        if not self.supplier_id.email:
            raise UserError(f"Supplier {self.supplier_id.name} has no email address.")

        template = self.env.ref(
            "plasticos_automation.email_template_supplier_confirmation",
            raise_if_not_found=False,
        )
        if not template:
            raise UserError("Supplier confirmation email template not found.")

        template.send_mail(self.id, force_send=True)
        self.supplier_confirmation_sent = fields.Datetime.now()
        self.message_post(body="Supplier confirmation request sent.")
        return True

    def _escalate_supplier_confirmation(self):
        """Create escalation activity for unconfirmed supplier."""
        self.ensure_one()
        has_activity = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", PLASTICOS_TRANSACTION),
                ("res_id", "=", self.id),
                ("summary", "ilike", "ESCALATION: Supplier confirmation"),
                ("date_deadline", "=", fields.Date.today()),
            ]
        )
        if has_activity:
            return

        supplier_name = self.supplier_id.name if self.supplier_id else "N/A"
        followup_count = self.supplier_confirmation_followup_count
        # Escalated to an Operations Manager, never to the salesperson or the acting user.
        # The transaction has no company of its own; its orders establish it.
        self.env["res.users"]._plasticos_escalate_to_manager(
            self,
            OPERATIONS_MANAGER_GROUP,
            summary=f"ESCALATION: Supplier confirmation pending on {self.name}",
            note=f"Supplier {supplier_name} has not confirmed after {followup_count} follow-ups.",
            label="supplier confirmation escalation",
            companies=self.sale_order_id.company_id | self.purchase_order_ids.company_id,
            one_open=False,
            exclude_users=self.user_id,
        )

    # ═════════════════════════════════════════════════════════
    # Action Methods (for UX smart buttons)
    # ═════════════════════════════════════════════════════════

    def action_view_supplier(self):
        """Open the supplier partner form."""
        self.ensure_one()
        if not self.supplier_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": RES_PARTNER,
            "res_id": self.supplier_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_buyer(self):
        """Open the buyer partner form."""
        self.ensure_one()
        if not self.buyer_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": RES_PARTNER,
            "res_id": self.buyer_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_lines(self):
        """Open transaction lines filtered to this transaction."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Lines — {self.name}",
            "res_model": "plasticos.transaction.line",
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.id)],
            "context": {"default_transaction_id": self.id},
        }

    # ═════════════════════════════════════════════════════════
    # Cron Methods (Logistics Enhancement)
    # ═════════════════════════════════════════════════════════

    @api.model
    def _cron_supplier_confirmation_followup(self):
        """Send follow-up emails for pending supplier confirmations.

        State flow: draft → active → pending_supplier → supplier_ready → ...
        By the time supplier_confirmation_sent is stamped, TX is typically
        in pending_supplier, not active. Search both states.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))",
            ["plasticos_transaction.cron_supplier_confirmation_followup"],
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping supplier confirmation followup cron: lock is already held.")
            return True

        try:
            threshold_hours = 24
            threshold_dt = fields.Datetime.now() - timedelta(hours=threshold_hours)

            pending = self.search(
                [
                    ("supplier_confirmation_sent", "!=", False),
                    ("supplier_confirmation_sent", "<", threshold_dt),
                    ("supplier_confirmation_received", "=", False),
                    ("state", "in", ["active", "pending_supplier"]),
                ],
                order="supplier_confirmation_sent asc",
                limit=100,
            )

            template = self.env.ref(
                "plasticos_automation.email_template_supplier_confirmation",
                raise_if_not_found=False,
            )

            for tx in pending:
                if tx.last_supplier_confirmation_followup_on:
                    last_followup_date = tx.last_supplier_confirmation_followup_on.date()
                    if last_followup_date == fields.Date.today():
                        continue

                try:
                    if template and tx.supplier_id and tx.supplier_id.email:
                        template.send_mail(tx.id, force_send=True)

                    tx.supplier_confirmation_followup_count += 1
                    tx.last_supplier_confirmation_followup_on = fields.Datetime.now()

                    if tx.supplier_confirmation_followup_count >= 3:
                        tx._escalate_supplier_confirmation()

                    _logger.info(
                        "Sent supplier confirmation follow-up #%d for TX %s",
                        tx.supplier_confirmation_followup_count,
                        tx.name,
                    )

                except Exception as e:
                    _logger.error("Failed to send follow-up for TX %s: %s", tx.name, str(e))
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))",
                ["plasticos_transaction.cron_supplier_confirmation_followup"],
            )

        return True

    @api.model
    def _cron_auto_create_delivery_orders(self):
        """Link existing pickings to transactions or trigger PO confirmation.

        Native Odoo creates pickings on PO confirm via purchase_stock.
        This cron:
        1. Finds TXs ready for DO (supplier confirmed, no DO linked)
        2. Checks if PO already has pickings -> link them
        3. If PO exists but no picking -> confirm PO (triggers native creation)
        4. Logs TXs that need manual PO creation
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))",
            ["plasticos_transaction.cron_auto_create_do"],
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping auto-create DO cron: lock is already held.")
            return True

        try:
            ready = self.search(
                [
                    ("is_supplier_confirmed", "=", True),
                    ("delivery_order_id", "=", False),
                    ("state", "in", ["supplier_ready", "active", "pending_supplier"]),
                ],
                order="supplier_confirmation_received asc",
                limit=100,
            )

            linked_count = 0
            for tx in ready:
                try:
                    linked = False
                    for po in tx.purchase_order_ids:
                        if po.picking_ids:
                            outgoing = po.picking_ids.filtered(
                                lambda p: p.picking_type_code == "outgoing" and p.state != "cancel"
                            )
                            if outgoing:
                                tx.delivery_order_id = outgoing[0].id
                                if tx.state == "supplier_ready":
                                    tx.action_mark_do_created()
                                _logger.info("Linked existing DO %s to TX %s", outgoing[0].name, tx.name)
                                linked_count += 1
                                linked = True
                                break
                        elif po.state == "draft":
                            po.button_confirm()
                            _logger.info("Confirmed PO %s for TX %s", po.name, tx.name)

                    if not linked and not tx.purchase_order_ids:
                        _logger.info("TX %s ready for DO but has no PO", tx.name)

                except Exception as e:
                    _logger.error("Failed to process TX %s: %s", tx.name, str(e))

            _logger.info("DO linkage cron: linked %d delivery orders", linked_count)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))",
                ["plasticos_transaction.cron_auto_create_do"],
            )
        return True

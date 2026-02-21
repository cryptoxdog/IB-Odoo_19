from odoo import api, fields, models
from odoo.exceptions import UserError


class PlasticosTransaction(models.Model):
    _name = "plasticos.transaction"
    _description = "Plasticos Transaction"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, copy=False, default="New")

    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
        help="Responsible salesperson. Uses Odoo native user_id convention.",
    )

    sale_order_id = fields.Many2one("sale.order")
    purchase_order_ids = fields.Many2many("purchase.order")

    load_id = fields.Many2one("plasticos.load")

    # ── Partner References (harvested from linda_logistics_v6) ──
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        domain=[("is_company", "=", True), ("supplier_rank", ">", 0)],
        tracking=True,
        index=True,
    )
    buyer_id = fields.Many2one(
        "res.partner",
        string="Buyer",
        domain=[("is_company", "=", True), ("customer_rank", ">", 0)],
        tracking=True,
        index=True,
    )
    carrier_id = fields.Many2one(
        "res.partner",
        string="Carrier",
        domain=[("is_company", "=", True)],
        tracking=True,
    )

    # ── Product Info (harvested) ───────────────────────────────
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        tracking=True,
    )
    quantity = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        tracking=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
    )
    unit_price = fields.Float(
        string="Unit Price",
        digits="Product Price",
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
        string="Delivery Term",
        default="fcfs",
        tracking=True,
    )
    freight_rate = fields.Float(
        string="Freight Rate",
        digits="Product Price",
        tracking=True,
    )
    freight_actual = fields.Float(
        string="Actual Freight Cost",
        digits="Product Price",
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

    # ── Quality Control ────────────────────────────────────────
    # NOTE: has_quality_claim is now a simple stored field.
    # The compute logic was moved to plasticos_claims module
    # which extends this model with claim_ids and recomputes this field.
    has_quality_claim = fields.Boolean(
        string="Has Quality Claim",
        default=False,
    )

    customer_invoice_id = fields.Many2one("account.move", domain=[("move_type", "=", "out_invoice")])

    vendor_bill_ids = fields.Many2many(
        "account.move", relation="plasticos_tx_vendor_rel", domain=[("move_type", "=", "in_invoice")]
    )

    freight_bill_ids = fields.Many2many(
        "account.move", relation="plasticos_tx_freight_rel", domain=[("move_type", "=", "in_invoice")]
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

    # Historical line items from cieTrade import
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

    commission_rule_id = fields.Many2one("plasticos.commission.rule")
    commission_amount = fields.Float(compute="_compute_commission", store=True)
    commission_locked = fields.Boolean(default=False, copy=False)
    commission_locked_amount = fields.Float(copy=False)

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
            ("supplier_ready", "Supplier Ready"),
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

    # ── Constraints (Odoo 19 models.Constraint) ──────────────
    _check_unique_name = models.Constraint(
        "unique(name)",
        "Transaction reference must be unique.",
    )

    # ── Computed Methods (harvested) ──────────────────────────
    @api.depends("expected_weight", "actual_weight")
    def _compute_weight_variance(self):
        for rec in self:
            if rec.expected_weight and rec.actual_weight:
                rec.weight_variance_percent = abs(rec.actual_weight - rec.expected_weight) / rec.expected_weight * 100
            else:
                rec.weight_variance_percent = 0.0

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
        "customer_invoice_id.amount_total",
        "vendor_bill_ids.amount_total",
        "freight_bill_ids.amount_total",
        "other_expenses",
        "freight_chargebacks",
        "lightweight_penalties",
    )
    def _compute_financials(self):
        """RevOps formula: gross_margin = revenue - costs + recoveries."""
        for rec in self:
            revenue = rec.customer_invoice_id.amount_total if rec.customer_invoice_id else 0.0
            purchase_cost = sum(rec.vendor_bill_ids.mapped("amount_total"))
            freight_cost = sum(rec.freight_bill_ids.mapped("amount_total"))
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
        """Net margin = gross margin - commission."""
        for rec in self:
            rec.net_margin = rec.gross_margin - (rec.commission_amount or 0.0)

    def _compute_chargebacks_penalties(self):
        """Sum recoveries from linked claims (plasticos.claim).

        Called by claim module when claims are resolved. Chargebacks and
        penalties are credits that reduce effective cost.
        """
        Claim = self.env.get("plasticos.claim")
        if not Claim:
            # Claims module not installed
            for rec in self:
                rec.freight_chargebacks = 0.0
                rec.lightweight_penalties = 0.0
            return
        for rec in self:
            claims = Claim.search(
                [
                    ("transaction_id", "=", rec.id),
                    ("state", "=", "resolved"),
                ]
            )
            rec.freight_chargebacks = sum(c.recovery_amount for c in claims if c.case_type == "freight_chargeback")
            rec.lightweight_penalties = sum(c.recovery_amount for c in claims if c.case_type == "lightweight_penalty")

    @api.depends("gross_margin", "commission_rule_id", "state", "commission_locked", "commission_locked_amount")
    def _compute_commission(self):
        service = self.env["plasticos.commission.service"]
        for rec in self:
            if rec.commission_locked:
                rec.commission_amount = rec.commission_locked_amount or 0.0
                continue
            rec.commission_amount = service.compute_commission(rec)

    @api.depends("create_date")
    def _compute_compliance(self):
        service = self.env.get("plasticos.compliance.service")
        if not service:
            # Compliance module not installed
            for rec in self:
                rec.compliance_status = "compliant"
            return
        for rec in self:
            if service.is_compliant("plasticos.transaction", rec.id):
                rec.compliance_status = "compliant"
            else:
                rec.compliance_status = "missing"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.transaction") or "New"
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if "state" in vals:
                allow = vals.get("state") == "active" or (
                    vals.get("state") == "closed" and vals.get("commission_locked") is True
                )
                if not allow:
                    raise UserError("State can only be changed via action methods.")
            if "name" in vals:
                raise UserError("Transaction reference cannot be modified.")
            if rec.state == "closed":
                protected = {
                    "sale_order_id",
                    "purchase_order_ids",
                    "customer_invoice_id",
                    "vendor_bill_ids",
                    "freight_bill_ids",
                    "commission_rule_id",
                }
                if protected.intersection(vals.keys()):
                    raise UserError("Closed transactions are immutable.")
            if rec.commission_locked and "commission_rule_id" in vals:
                raise UserError("Commission cannot be modified after lock.")
            if rec.customer_invoice_id and "customer_invoice_id" in vals:
                if vals["customer_invoice_id"] != rec.customer_invoice_id.id:
                    raise UserError("Customer invoice cannot be reassigned once set.")
            if "vendor_bill_ids" in vals:
                for cmd in vals["vendor_bill_ids"]:
                    if cmd[0] == 4:
                        other = self.search(
                            [
                                ("vendor_bill_ids", "in", [cmd[1]]),
                                ("id", "!=", rec.id),
                            ],
                            limit=1,
                        )
                        if other:
                            raise UserError("Vendor bill already linked to another transaction.")
                    elif cmd[0] == 6:
                        for bid in cmd[2]:
                            other = self.search(
                                [
                                    ("vendor_bill_ids", "in", [bid]),
                                    ("id", "!=", rec.id),
                                ],
                                limit=1,
                            )
                            if other:
                                raise UserError("Vendor bill already linked to another transaction.")
            if "freight_bill_ids" in vals:
                for cmd in vals["freight_bill_ids"]:
                    if cmd[0] == 4:
                        other = self.search(
                            [
                                ("freight_bill_ids", "in", [cmd[1]]),
                                ("id", "!=", rec.id),
                            ],
                            limit=1,
                        )
                        if other:
                            raise UserError("Freight bill already linked to another transaction.")
                    elif cmd[0] == 6:
                        for bid in cmd[2]:
                            other = self.search(
                                [
                                    ("freight_bill_ids", "in", [bid]),
                                    ("id", "!=", rec.id),
                                ],
                                limit=1,
                            )
                            if other:
                                raise UserError("Freight bill already linked to another transaction.")
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.customer_invoice_id or rec.vendor_bill_ids or rec.freight_bill_ids:
                raise UserError("Cannot delete transaction linked to accounting records.")
            if rec.state == "closed":
                raise UserError("Closed transactions cannot be deleted.")
        return super().unlink()

    def action_activate(self):
        self.state = "active"

    def action_close(self):
        service_docs = self.env.get("plasticos.compliance.service")
        service_commission = self.env.get("plasticos.commission.service")

        for rec in self:
            self.env.cr.execute(
                "SELECT id FROM plasticos_transaction WHERE id = %s FOR UPDATE",
                (rec.id,),
            )
            if rec.state == "closed":
                raise UserError("Transaction is already closed.")
            if not rec.customer_invoice_id or rec.customer_invoice_id.state != "posted":
                raise UserError("Customer invoice must be posted.")

            if any(bill.state != "posted" for bill in rec.vendor_bill_ids):
                raise UserError("Vendor bills must be posted.")

            if rec.load_id and rec.load_id.state != "closed":
                raise UserError("Logistics must be closed.")

            if service_docs and not service_docs.is_compliant("plasticos.transaction", rec.id):
                raise UserError("Required documents missing.")

            if not self.env.user.has_group("plasticos_transaction.group_plasticos_manager"):
                raise UserError("Only Plasticos Managers can close transactions.")

            if rec.gross_margin < 0:
                raise UserError("Cannot close transaction with negative gross margin.")

            amount = service_commission.compute_commission(rec) if service_commission else 0.0
            rec.write(
                {
                    "commission_locked_amount": amount,
                    "commission_locked": True,
                    "state": "closed",
                }
            )

from odoo import models, fields, api
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

    customer_invoice_id = fields.Many2one(
        "account.move",
        domain=[("move_type", "=", "out_invoice")]
    )

    vendor_bill_ids = fields.Many2many(
        "account.move",
        relation="plasticos_tx_vendor_rel",
        domain=[("move_type", "=", "in_invoice")]
    )

    freight_bill_ids = fields.Many2many(
        "account.move",
        relation="plasticos_tx_freight_rel",
        domain=[("move_type", "=", "in_invoice")]
    )

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

    revenue_total = fields.Float(compute="_compute_financials", store=True)
    cost_total = fields.Float(compute="_compute_financials", store=True)
    gross_margin = fields.Float(compute="_compute_financials", store=True)
    net_margin = fields.Float(compute="_compute_financials", store=True)

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

    state = fields.Selection([
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed")
    ], default="draft", tracking=True, index=True)

    # ── Constraints (Odoo 19 models.Constraint) ──────────────
    _check_unique_name = models.Constraint(
        "unique(name)",
        "Transaction reference must be unique.",
    )

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
        "freight_bill_ids.amount_total"
    )
    def _compute_financials(self):
        for rec in self:
            revenue = rec.customer_invoice_id.amount_total if rec.customer_invoice_id else 0.0
            vendor_cost = sum(rec.vendor_bill_ids.mapped("amount_total"))
            freight_cost = sum(rec.freight_bill_ids.mapped("amount_total"))
            cost = vendor_cost + freight_cost
            rec.revenue_total = revenue
            rec.cost_total = cost
            rec.gross_margin = revenue - cost
            rec.net_margin = revenue - cost

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
        service = self.env["plasticos.compliance.service"]
        for rec in self:
            if service.is_compliant("plasticos.transaction", rec.id):
                rec.compliance_status = "compliant"
            else:
                rec.compliance_status = "missing"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("plasticos.transaction") or "New"
                )
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if "state" in vals:
                allow = (
                    vals.get("state") == "active"
                    or (vals.get("state") == "closed" and vals.get("commission_locked") is True)
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
                        other = self.search([
                            ("vendor_bill_ids", "in", [cmd[1]]),
                            ("id", "!=", rec.id),
                        ], limit=1)
                        if other:
                            raise UserError("Vendor bill already linked to another transaction.")
                    elif cmd[0] == 6:
                        for bid in cmd[2]:
                            other = self.search([
                                ("vendor_bill_ids", "in", [bid]),
                                ("id", "!=", rec.id),
                            ], limit=1)
                            if other:
                                raise UserError("Vendor bill already linked to another transaction.")
            if "freight_bill_ids" in vals:
                for cmd in vals["freight_bill_ids"]:
                    if cmd[0] == 4:
                        other = self.search([
                            ("freight_bill_ids", "in", [cmd[1]]),
                            ("id", "!=", rec.id),
                        ], limit=1)
                        if other:
                            raise UserError("Freight bill already linked to another transaction.")
                    elif cmd[0] == 6:
                        for bid in cmd[2]:
                            other = self.search([
                                ("freight_bill_ids", "in", [bid]),
                                ("id", "!=", rec.id),
                            ], limit=1)
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
        service_docs = self.env["plasticos.compliance.service"]
        service_commission = self.env["plasticos.commission.service"]

        for rec in self:
            self.env.cr.execute(
                "SELECT id FROM plasticos_transaction WHERE id = %s FOR UPDATE",
                (rec.id,),
            )
            if not rec.customer_invoice_id or rec.customer_invoice_id.state != "posted":
                raise UserError("Customer invoice must be posted.")

            if any(bill.state != "posted" for bill in rec.vendor_bill_ids):
                raise UserError("Vendor bills must be posted.")

            if rec.load_id and rec.load_id.state != "closed":
                raise UserError("Logistics must be closed.")

            if not service_docs.is_compliant("plasticos.transaction", rec.id):
                raise UserError("Required documents missing.")

            if not self.env.user.has_group("plasticos_transaction.group_plasticos_manager"):
                raise UserError("Only Plasticos Managers can close transactions.")

            if rec.gross_margin < 0:
                raise UserError("Cannot close transaction with negative gross margin.")

            amount = service_commission.compute_commission(rec)
            rec.write({
                "commission_locked_amount": amount,
                "commission_locked": True,
                "state": "closed",
            })

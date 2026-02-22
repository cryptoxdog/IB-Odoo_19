"""
Transaction Line model for storing cieTrade WksDetail records.

Each line represents a material line item within a transaction,
capturing weight, pricing, and material specifications.
"""

from odoo import api, fields, models


class PlasticosTransactionLine(models.Model):
    _name = "plasticos.transaction.line"
    _description = "Transaction Line Item"
    _order = "transaction_id, id"

    transaction_id = fields.Many2one(
        "plasticos.transaction",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # cieTrade identifiers
    detail_id = fields.Char(
        string="Detail ID",
        index=True,
        help="Original DetailID from cieTrade",
    )
    grade_id = fields.Char(
        string="Grade ID",
        index=True,
        help="Material grade code from cieTrade",
    )

    # Description
    description = fields.Char(
        string="Invoice Description",
        help="Material description as it appears on invoice",
    )

    # Weight
    sale_weight = fields.Float(
        string="Sale Weight",
        digits=(16, 6),
        help="Weight sold to customer",
    )
    purchase_weight = fields.Float(
        string="Purchase Weight",
        digits=(16, 6),
        help="Weight purchased from supplier",
    )
    weight_uom = fields.Selection(
        [
            ("L", "Pounds (lbs)"),
            ("S", "Short Tons"),
            ("E", "Each"),
        ],
        string="Weight UOM",
        default="L",
    )

    # Pricing
    sale_price = fields.Float(
        string="Sale Price",
        digits=(16, 5),
        help="Price per unit sold",
    )
    purchase_price = fields.Float(
        string="Purchase Price",
        digits=(16, 5),
        help="Price per unit purchased",
    )
    sale_amount = fields.Float(
        string="Sale Amount",
        digits=(16, 2),
        help="Total sale amount (weight * price)",
    )
    purchase_amount = fields.Float(
        string="Purchase Amount",
        digits=(16, 2),
        help="Total purchase amount (weight * price)",
    )

    # Computed margin
    margin = fields.Float(
        string="Line Margin",
        compute="_compute_margin",
        store=True,
        digits=(16, 2),
    )

    # Additional attributes
    specifications = fields.Text(
        string="Specifications",
        help="Material specifications and notes",
    )
    lot_no = fields.Char(string="Lot Number")
    container_no = fields.Char(string="Container Number")
    unit_type = fields.Selection(
        [
            ("B", "Bale"),
            ("G", "Gaylord"),
            ("X", "Box"),
            ("P", "Pallet"),
            ("L", "Loose"),
            ("A", "Bag"),
            ("F", "Flat"),
            ("H", "Hopper"),
            ("C", "Container"),
            ("E", "Each"),
            ("O", "Other"),
        ],
        string="Unit Type",
        help="Container/packaging type",
    )
    units = fields.Float(
        string="Units",
        default=1.0,
        digits=(16, 2),
        help="Number of containers (bales, gaylords, boxes, etc.)",
    )
    condition = fields.Char(string="Condition")
    color = fields.Char(string="Color")
    seal_no = fields.Char(string="Seal Number")

    # PO references
    sale_po = fields.Char(string="Sale PO")
    purchase_po = fields.Char(string="Purchase PO")

    # Normalized weight in lbs for reporting
    sale_weight_lbs = fields.Float(
        string="Sale Weight (lbs)",
        compute="_compute_weight_lbs",
        store=True,
        digits=(16, 2),
        help="Weight normalized to pounds",
    )

    @api.depends("sale_weight", "weight_uom")
    def _compute_weight_lbs(self):
        """Convert weight to lbs for consistent reporting."""
        for rec in self:
            if rec.weight_uom == "L":
                rec.sale_weight_lbs = rec.sale_weight
            elif rec.weight_uom == "S":
                # Short tons to lbs (1 short ton = 2000 lbs)
                rec.sale_weight_lbs = rec.sale_weight * 2000
            elif rec.weight_uom == "E":
                # Each - no weight conversion, keep as-is
                rec.sale_weight_lbs = rec.sale_weight
            else:
                rec.sale_weight_lbs = rec.sale_weight

    @api.depends("sale_amount", "purchase_amount")
    def _compute_margin(self):
        for rec in self:
            rec.margin = rec.sale_amount - rec.purchase_amount

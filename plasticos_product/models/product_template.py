from odoo import api, fields, models


class ProductTemplate(models.Model):
    """
    Extends product.template for plastics trading.

    Products are auto-created from plasticos.polymer master data (1:1 sync).
    The product represents the POLYMER only. All other material details
    (color, form, packaging, source, filler, attributes) live on PO/SO lines.

    Example flow:
    - Product: "HDPE" (just the polymer)
    - PO Line: HDPE + Blue + Regrind + Gaylords + Post-Industrial + Clean
    - Display: "HDPE Blue Regrind - Gaylords - Post-Industrial - Clean"
    """

    _inherit = "product.template"

    # ── Link to Polymer Master ────────────────────────────────────
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        index=True,
        ondelete="restrict",
        help="Link to polymer master record. Products are auto-synced from polymers.",
    )

    # ── Flag for auto-created polymer products ────────────────────
    is_polymer_product = fields.Boolean(
        string="Is Polymer Product",
        default=False,
        help="True if this product was auto-created from a polymer record.",
    )


class PlasticosPolymer(models.Model):
    """Extend polymer to auto-create products."""

    _inherit = "plasticos.polymer"

    product_id = fields.Many2one(
        "product.template",
        string="Product",
        readonly=True,
        help="Auto-created product for this polymer.",
        ondelete="restrict",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-create product when polymer is created."""
        records = super().create(vals_list)
        for rec in records:
            rec._ensure_product()
        return records

    def write(self, vals):
        """Sync product when polymer is updated."""
        res = super().write(vals)
        if "name" in vals or "full_name" in vals:
            for rec in self:
                rec._sync_product()
        return res

    def _ensure_product(self):
        """Create product if it doesn't exist."""
        self.ensure_one()
        if self.product_id:
            return
        Product = self.env["product.template"]
        product = Product.create(
            {
                "name": self.name,
                "type": "consu",
                "polymer_id": self.id,
                "is_polymer_product": True,
                "description": self.full_name or self.name,
            }
        )
        self.product_id = product.id

    def _sync_product(self):
        """Sync product name with polymer."""
        self.ensure_one()
        if self.product_id:
            self.product_id.write(
                {
                    "name": self.name,
                    "description": self.full_name or self.name,
                }
            )

    def action_create_products(self):
        """Batch action to create products for all polymers."""
        for rec in self:
            rec._ensure_product()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Products Created",
                "message": f"Created/verified products for {len(self)} polymers.",
                "type": "success",
            },
        }

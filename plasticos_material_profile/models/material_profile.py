from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosMaterialProfile(models.Model):
    _name = "plasticos.material.profile"
    _description = "Material Identity Profile"
    _inherit = ["mail.thread"]
    _order = "partner_id, polymer_id"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        domain="[('parent_id','!=',False)]",
        ondelete="cascade",
        tracking=True,
    )

    active = fields.Boolean(default=True)

    # ── Identity ─────────────────────────────────────────────
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Canonical polymer type from the master registry.",
    )

    # Backward-compatible computed field — reads polymer_id.code
    polymer = fields.Selection(
        [
            # Commodity
            ("pp", "PP"),
            ("pp_pe", "PP/PE"),
            ("hdpe", "HDPE"),
            ("hdpe_hmw", "HDPE HMW"),
            ("ldpe", "LDPE"),
            ("lldpe", "LLDPE"),
            ("plastic_pallets", "Plastic Pallets"),
            ("gaylord_boxes", "Gaylord Boxes"),
            ("pet", "PET"),
            ("abs", "ABS"),
            ("hips", "HIPS"),
            ("ps", "PS"),
            ("eps", "EPS"),
            ("pvc", "PVC"),
            ("mixed", "Mixed"),
            # Engineering
            ("pmma", "PMMA"),
            ("pc", "PC"),
            ("pc_pmma", "PC-PMMA"),
            ("nylon", "Nylon"),
            ("pbt", "PBT"),
            ("pom", "POM"),
            ("ppo", "PPO"),
            # Specialty
            ("tpe", "TPE"),
            ("tpo", "TPO"),
            ("bopp", "BOPP"),
            ("eva", "EVA"),
            ("mrp", "MRP"),
            ("ewaste", "E-Waste"),
            ("occ", "OCC"),
            ("metal", "Metal"),
        ],
        string="Polymer Code",
        compute="_compute_polymer_code",
        store=True,
        index=True,
        help="Auto-populated from polymer_id. Kept for backward compatibility.",
    )

    sub_grade = fields.Char()

    # ── Form (Many2one to master) ────────────────────────────
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Canonical material form from the master registry.",
    )
    # Backward-compatible computed field
    form = fields.Selection(
        [
            ("bales", "Bales"),
            ("film", "Film"),
            ("regrind", "Regrind"),
            ("flake", "Flake"),
            ("rollstock", "Rollstock"),
            ("pellets", "Pellets"),
            ("purge", "Purge"),
            ("chopped", "Chopped"),
            ("shred", "Shred"),
            ("densified", "Densified"),
            ("parts", "Parts"),
            ("sheet", "Sheet"),
            ("powder", "Powder"),
            ("logs", "Logs"),
            ("floorsweep", "Floorsweep"),
            ("drums", "Drums"),
            ("buckets", "Buckets"),
            ("bottles", "Bottles"),
            ("loose", "Loose"),
            ("pallets", "Pallets"),
            ("other", "Other"),
        ],
        string="Form Code",
        compute="_compute_form_code",
        store=True,
        index=True,
        help="Auto-populated from form_id. Kept for backward compatibility.",
    )

    # ── Color (Many2one to master) ───────────────────────────
    color_id = fields.Many2one(
        "plasticos.material.color",
        string="Color",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Canonical material color from the master registry.",
    )
    # Backward-compatible computed field
    color = fields.Selection(
        [
            ("clear", "Clear"),
            ("natural", "Natural"),
            ("white", "White"),
            ("black", "Black"),
            ("mixed", "Mixed"),
            ("blue", "Blue"),
            ("blue_white", "Blue/White"),
            ("red", "Red"),
            ("green", "Green"),
            ("yellow", "Yellow"),
            ("orange", "Orange"),
            ("gray", "Gray"),
        ],
        string="Color Code",
        compute="_compute_color_code",
        store=True,
        help="Auto-populated from color_id. Kept for backward compatibility.",
    )
    color_flexibility = fields.Selection(
        [
            ("exact", "Exact Match Only"),
            ("similar", "Similar Shades OK"),
            ("any", "Any Color"),
        ],
        help="How flexible the buyer/seller is on color.",
    )

    # ── Source Type (Many2one to master) ─────────────────────
    source_type_id = fields.Many2one(
        "plasticos.source.type",
        string="Source Type",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Canonical source type from the master registry.",
    )
    # Backward-compatible computed field
    source_type = fields.Selection(
        [
            ("post_consumer", "Post-Consumer"),
            ("post_industrial", "Post-Industrial"),
            ("post_commercial", "Post-Commercial"),
            ("agricultural", "Agricultural"),
            ("prime", "Prime / Virgin"),
            ("wide_spec", "Wide Spec"),
            ("off_spec", "Off Spec"),
            ("ocean_recovered", "Ocean Recovered"),
        ],
        string="Source Type Code",
        compute="_compute_source_type_code",
        store=True,
        help="Auto-populated from source_type_id. Kept for backward compatibility.",
    )

    origin_process_type = fields.Selection(
        [
            ("injection", "Injection Molding"),
            ("extrusion", "Extrusion"),
            ("blow_mold", "Blow Molding"),
            ("thermoform", "Thermoforming"),
            ("rotomold", "Rotational Molding"),
            ("film_blown", "Film Blown"),
            ("film_cast", "Film Cast"),
            ("compounding", "Compounding"),
            ("other", "Other"),
        ],
    )

    previously_washed = fields.Boolean()
    previously_pelletized = fields.Boolean()

    # ── Material Attributes (multi-select) ─────────────────────
    material_attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
        string="Material Attributes",
        help="Condition attributes: Clean, Metalized, With Metal, Printed, etc.",
    )

    # Alias for consistency with order lines
    attribute_ids = fields.Many2many(
        related="material_attribute_ids",
        string="Attributes",
    )

    # ── Filler Type ────────────────────────────────────────────
    filler_type_id = fields.Many2one(
        "plasticos.filler.type",
        string="Filler Type",
        index=True,
        ondelete="restrict",
        help="Glass filled, talc filled, etc.",
    )
    filler_pct = fields.Float(
        string="Filler %",
        help="Percentage of filler content (e.g., 30 for 30% glass filled).",
    )

    # ── Quality ──────────────────────────────────────────────
    melt_flow_index = fields.Float(index=True)
    density = fields.Float()
    moisture_percent = fields.Float()
    contamination_percent = fields.Float(index=True)
    # Boolean flags linked to material_attribute_ids
    has_metal = fields.Boolean(
        string="Has Metal",
        help="Contains metal contamination. Synced with 'With Metal'/'No Metal' attributes.",
    )
    is_metalized = fields.Boolean(
        string="Metalized Film",
        help="Film with metallic coating (e.g., chip bags). Synced with 'Metalized' attribute.",
    )
    contains_fr = fields.Boolean(string="Contains FR")

    # ── Volume ───────────────────────────────────────────────
    avg_lot_size_lbs = fields.Float(index=True)
    min_lot_size_lbs = fields.Float()
    max_lot_size_lbs = fields.Float()
    monthly_volume_lbs = fields.Float(index=True)

    frequency = fields.Selection(
        [
            ("one_time", "One Time"),
            ("weekly", "Weekly"),
            ("biweekly", "Biweekly"),
            ("monthly", "Monthly"),
            ("contract", "Contract"),
        ],
    )

    # ── Origin Form (what it was before processing) ──────────
    origin_form_id = fields.Many2one(
        "plasticos.material.form",
        string="Origin Form",
        help="What the material was before processing (Drums, Bottles, Film). Optional.",
    )

    # ── Packaging ────────────────────────────────────────────
    packaging_type_id = fields.Many2one(
        "plasticos.packaging.type",
        string="Packaging",
        help="How the material is packaged/shipped (Gaylords, Super Sacks, Bales). Optional.",
    )

    avg_truckloads_per_month = fields.Float()

    # ── Compliance ───────────────────────────────────────────
    food_grade = fields.Boolean()
    medical_grade = fields.Boolean()
    certification_notes = fields.Text()

    # ── AI Enrichment ────────────────────────────────────────
    freeform_notes = fields.Text()

    # ── Navigation: Related Record Counts ──────────────────────
    # NOTE: intake_count is added by plasticos_intake module via inheritance
    po_line_count = fields.Integer(
        string="PO Lines",
        compute="_compute_po_line_count",
    )
    so_line_count = fields.Integer(
        string="SO Lines",
        compute="_compute_so_line_count",
    )

    # Computed: Parent company for quick navigation
    company_id = fields.Many2one(
        related="partner_id.parent_id",
        string="Company",
        store=True,
    )

    # ═════════════════════════════════════════════════════════
    # Constraints (Odoo 19 models.Constraint)
    # ═════════════════════════════════════════════════════════

    _check_unique_partner_polymer = models.Constraint(
        "unique(partner_id, polymer_id, form_id)",
        "A facility may only have one profile per polymer + form combination.",
    )

    # ═════════════════════════════════════════════════════════
    # Computed
    # ═════════════════════════════════════════════════════════

    @api.depends("polymer_id", "polymer_id.code")
    def _compute_polymer_code(self):
        for rec in self:
            rec.polymer = rec.polymer_id.code if rec.polymer_id else False

    @api.depends("form_id", "form_id.code")
    def _compute_form_code(self):
        for rec in self:
            rec.form = rec.form_id.code if rec.form_id else False

    @api.depends("color_id", "color_id.code")
    def _compute_color_code(self):
        for rec in self:
            rec.color = rec.color_id.code if rec.color_id else False

    @api.depends("source_type_id", "source_type_id.code")
    def _compute_source_type_code(self):
        for rec in self:
            rec.source_type = rec.source_type_id.code if rec.source_type_id else False

    def _compute_po_line_count(self):
        """Count PO lines linked to this profile.

        Requires plasticos_order_lines module to be installed.
        Returns 0 if material_profile_id field doesn't exist on purchase.order.line.
        """
        POLine = self.env["purchase.order.line"]
        has_field = "material_profile_id" in POLine._fields
        for rec in self:
            rec.po_line_count = POLine.search_count([("material_profile_id", "=", rec.id)]) if has_field else 0

    def _compute_so_line_count(self):
        """Count SO lines linked to this profile.

        Requires plasticos_order_lines module to be installed.
        Returns 0 if material_profile_id field doesn't exist on sale.order.line.
        """
        SOLine = self.env["sale.order.line"]
        has_field = "material_profile_id" in SOLine._fields
        for rec in self:
            rec.so_line_count = SOLine.search_count([("material_profile_id", "=", rec.id)]) if has_field else 0

    # ═════════════════════════════════════════════════════════
    # Navigation Actions (Jump To)
    # ═════════════════════════════════════════════════════════
    # NOTE: action_view_intakes and action_create_intake are added by
    # plasticos_intake module via inheritance to avoid circular dependency.

    def action_view_po_lines(self):
        """Navigate to PO lines linked to this profile.

        Requires plasticos_order_lines module to be installed.
        """
        self.ensure_one()
        POLine = self.env["purchase.order.line"]
        if "material_profile_id" not in POLine._fields:
            raise ValidationError(
                "PO line tracking requires the 'PlasticOS Order Lines' module.\n\n"
                "Install 'plasticos_order_lines' from Apps to enable this feature."
            )
        return {
            "type": "ir.actions.act_window",
            "name": f"Purchase Lines - {self.polymer_id.name}",
            "res_model": "purchase.order.line",
            "view_mode": "list,form",
            "domain": [("material_profile_id", "=", self.id)],
        }

    def action_view_so_lines(self):
        """Navigate to SO lines linked to this profile.

        Requires plasticos_order_lines module to be installed.
        """
        self.ensure_one()
        SOLine = self.env["sale.order.line"]
        if "material_profile_id" not in SOLine._fields:
            raise ValidationError(
                "SO line tracking requires the 'PlasticOS Order Lines' module.\n\n"
                "Install 'plasticos_order_lines' from Apps to enable this feature."
            )
        return {
            "type": "ir.actions.act_window",
            "name": f"Sale Lines - {self.polymer_id.name}",
            "res_model": "sale.order.line",
            "view_mode": "list,form",
            "domain": [("material_profile_id", "=", self.id)],
        }

    def action_view_facility(self):
        """Navigate to facility (partner_id)."""
        self.ensure_one()
        if not self.partner_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": self.partner_id.name,
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.partner_id.id,
        }

    def action_view_company(self):
        """Navigate to parent company."""
        self.ensure_one()
        if not self.company_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": self.company_id.name,
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.company_id.id,
        }

    # ═════════════════════════════════════════════════════════
    # Attribute ↔ Boolean Sync
    # ═════════════════════════════════════════════════════════

    @api.onchange("material_attribute_ids")
    def _onchange_material_attributes(self):
        """Sync boolean fields when attributes change."""
        attr_codes = set(self.material_attribute_ids.mapped("code"))
        # Metal contamination: With Metal vs No Metal
        if "with_metal" in attr_codes:
            self.has_metal = True
        elif "no_metal" in attr_codes:
            self.has_metal = False
        # Metalized film coating
        if "metalized" in attr_codes:
            self.is_metalized = True
        else:
            self.is_metalized = False

    @api.onchange("has_metal")
    def _onchange_has_metal(self):
        """Sync attributes when has_metal boolean changes."""
        Attribute = self.env["plasticos.material.attribute"]
        with_metal = Attribute.search([("code", "=", "with_metal")], limit=1)
        no_metal = Attribute.search([("code", "=", "no_metal")], limit=1)
        if self.has_metal:
            # Add With Metal, remove No Metal
            if with_metal and with_metal not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, with_metal.id)]
            if no_metal and no_metal in self.material_attribute_ids:
                self.material_attribute_ids = [(3, no_metal.id)]
        else:
            # Add No Metal, remove With Metal
            if no_metal and no_metal not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, no_metal.id)]
            if with_metal and with_metal in self.material_attribute_ids:
                self.material_attribute_ids = [(3, with_metal.id)]

    @api.onchange("is_metalized")
    def _onchange_is_metalized(self):
        """Sync attributes when is_metalized boolean changes."""
        Attribute = self.env["plasticos.material.attribute"]
        metalized = Attribute.search([("code", "=", "metalized")], limit=1)
        if self.is_metalized:
            if metalized and metalized not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, metalized.id)]
        else:
            if metalized and metalized in self.material_attribute_ids:
                self.material_attribute_ids = [(3, metalized.id)]

    # ═════════════════════════════════════════════════════════
    # Validation
    # ═════════════════════════════════════════════════════════

    @api.constrains("partner_id")
    def _check_partner_is_facility(self):
        for rec in self:
            if not rec.partner_id.parent_id:
                raise ValidationError("Material profiles can only attach to facility-level partners.")

    # ═════════════════════════════════════════════════════════
    # CRUD
    # ═════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._emit_material_packet()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._emit_material_packet()
        return res

    # ═════════════════════════════════════════════════════════
    # Actions: Make PO
    # ═════════════════════════════════════════════════════════
    # NOTE: action_create_intake is added by plasticos_intake module.

    def action_create_purchase_order(self):
        """Create a PO with a line pre-filled from this material profile.

        Requires plasticos_order_lines module for full material spec on PO lines.
        """
        self.ensure_one()

        # Require plasticos_order_lines for material spec fields
        POLine = self.env["purchase.order.line"]
        if "material_profile_id" not in POLine._fields:
            raise ValidationError(
                "Creating POs from material profiles requires the 'PlasticOS Order Lines' module.\n\n"
                "Install 'plasticos_order_lines' from Apps to enable this feature."
            )

        # Check if product module is installed and polymer has product_id field
        product_id = False
        product_uom_id = False
        if hasattr(self.polymer_id, "product_id") and self.polymer_id.product_id:
            product_id = self.polymer_id.product_id.id
            product_uom_id = self.polymer_id.product_id.uom_id.id if self.polymer_id.product_id.uom_id else False
        elif hasattr(self.polymer_id, "_ensure_product"):
            # Product module installed but no product yet - create one
            self.polymer_id._ensure_product()
            if self.polymer_id.product_id:
                product_id = self.polymer_id.product_id.id
                product_uom_id = self.polymer_id.product_id.uom_id.id if self.polymer_id.product_id.uom_id else False

        line_vals = {
            "product_id": product_id,
            "name": f"{self.polymer_id.name} - {self.partner_id.name}",
            "product_qty": 1,
            "product_uom": product_uom_id,
            "material_profile_id": self.id,
            "color_id": self.color_id.id if self.color_id else False,
            "form_id": self.form_id.id if self.form_id else False,
            "packaging_type_id": self.packaging_type_id.id if self.packaging_type_id else False,
            "source_type_id": self.source_type_id.id if self.source_type_id else False,
            "filler_type_id": self.filler_type_id.id if self.filler_type_id else False,
            "material_attribute_ids": [(6, 0, self.material_attribute_ids.ids)],
        }

        return {
            "type": "ir.actions.act_window",
            "name": "Create Purchase Order",
            "res_model": "purchase.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.partner_id.parent_id.id if self.partner_id.parent_id else self.partner_id.id,
                "default_order_line": [(0, 0, line_vals)],
            },
        }

    # ═════════════════════════════════════════════════════════
    # Capability Packet (stub for L9 adapter)
    # ═════════════════════════════════════════════════════════

    def _emit_material_packet(self):
        for rec in self:
            packet = {
                "partner_id": rec.partner_id.id,
                "polymer": rec.polymer_id.code if rec.polymer_id else None,
                "polymer_name": rec.polymer_id.name if rec.polymer_id else None,
                "form": rec.form_id.code if rec.form_id else None,
                "form_name": rec.form_id.name if rec.form_id else None,
                "color": rec.color_id.code if rec.color_id else None,
                "color_name": rec.color_id.name if rec.color_id else None,
                "attributes": rec.material_attribute_ids.mapped("code"),
                "quality": {
                    "mfi": rec.melt_flow_index,
                    "density": rec.density,
                    "moisture": rec.moisture_percent,
                    "contamination": rec.contamination_percent,
                    "has_metal": rec.has_metal,
                    "is_metalized": rec.is_metalized,
                    "fr": rec.contains_fr,
                },
                "volume": {
                    "avg_lot": rec.avg_lot_size_lbs,
                    "monthly": rec.monthly_volume_lbs,
                    "frequency": rec.frequency,
                },
                "source": {
                    "source_type": rec.source_type_id.code if rec.source_type_id else None,
                    "source_type_name": rec.source_type_id.name if rec.source_type_id else None,
                    "origin_process": rec.origin_process_type,
                    "washed": rec.previously_washed,
                    "pelletized": rec.previously_pelletized,
                },
                "filler": {
                    "type": rec.filler_type_id.code if rec.filler_type_id else None,
                    "type_name": rec.filler_type_id.name if rec.filler_type_id else None,
                    "pct": rec.filler_pct,
                },
            }
            # Stub only — L9 adapter will consume this.
            _ = packet

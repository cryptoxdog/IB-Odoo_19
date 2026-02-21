from odoo import models, fields, api
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
            ("hdpe", "HDPE"),
            ("ldpe", "LDPE"),
            ("lldpe", "LLDPE"),
            ("pp", "PP"),
            ("pet", "PET"),
            ("rpet", "rPET"),
            ("ps", "PS"),
            ("hips", "HIPS"),
            ("pvc", "PVC"),
            ("eva", "EVA"),
            ("abs", "ABS"),
            ("nylon", "Nylon"),
            ("pc", "PC"),
            ("pbt", "PBT"),
            ("pom", "POM"),
            ("pmma", "PMMA"),
            ("ppo", "PPO"),
            ("tpe", "TPE"),
            ("tpu", "TPU"),
            ("pla", "PLA"),
            ("ewaste", "E-Waste"),
            ("other", "Other"),
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
            ("bale", "Bale"),
            ("regrind", "Regrind"),
            ("flake", "Flake"),
            ("pellet", "Pellet"),
            ("rollstock", "Rollstock"),
            ("purge", "Purge"),
            ("lump", "Lump"),
            ("film", "Film"),
            ("sheet", "Sheet"),
            ("powder", "Powder"),
            ("parts", "Parts"),
            ("re_useable", "Re-Useable"),
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
            ("natural", "Natural"),
            ("white", "White"),
            ("black", "Black"),
            ("clear", "Clear"),
            ("blue", "Blue"),
            ("red", "Red"),
            ("green", "Green"),
            ("yellow", "Yellow"),
            ("orange", "Orange"),
            ("gray", "Gray"),
            ("brown", "Brown"),
            ("mixed", "Mixed"),
            ("other", "Other"),
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
            ("post_industrial", "Post-Industrial"),
            ("post_consumer", "Post-Consumer"),
            ("post_commercial", "Post-Commercial"),
            ("agricultural", "Agricultural"),
            ("prime", "Prime / Virgin"),
            ("wide_spec", "Wide Spec"),
            ("off_spec", "Off Spec"),
            ("ocean_recovered", "Ocean Recovered"),
            ("unknown", "Unknown"),
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

    # ── Quality ──────────────────────────────────────────────
    melt_flow_index = fields.Float(index=True)
    density = fields.Float()
    moisture_percent = fields.Float()
    contamination_percent = fields.Float(index=True)
    contains_metal = fields.Boolean()
    contains_fr = fields.Boolean()

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

    # ── Packaging ────────────────────────────────────────────
    packaging_type = fields.Selection(
        [
            ("gaylord", "Gaylord"),
            ("supersack", "Super Sack"),
            ("loose", "Loose"),
            ("palletized", "Palletized"),
            ("bulk_trailer", "Bulk Trailer"),
            ("other", "Other"),
        ],
    )

    avg_truckloads_per_month = fields.Float()

    # ── Compliance ───────────────────────────────────────────
    food_grade = fields.Boolean()
    medical_grade = fields.Boolean()
    certification_notes = fields.Text()

    # ── AI Enrichment ────────────────────────────────────────
    freeform_notes = fields.Text()

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

    # ═════════════════════════════════════════════════════════
    # Validation
    # ═════════════════════════════════════════════════════════

    @api.constrains("partner_id")
    def _check_partner_is_facility(self):
        for rec in self:
            if not rec.partner_id.parent_id:
                raise ValidationError(
                    "Material profiles can only attach to facility-level partners."
                )

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
                "quality": {
                    "mfi": rec.melt_flow_index,
                    "density": rec.density,
                    "moisture": rec.moisture_percent,
                    "contamination": rec.contamination_percent,
                    "metal": rec.contains_metal,
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
            }
            # Stub only — L9 adapter will consume this.
            _ = packet

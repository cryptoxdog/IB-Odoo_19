from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PlastosMaterialProfile(models.Model):
    _name = "plasticos.material.profile"
    _description = "Material Identity Profile"
    _inherit = ["mail.thread"]
    _order = "partner_id, polymer"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        domain="[('parent_id','!=',False)]",
        ondelete="cascade",
        tracking=True
    )

    active = fields.Boolean(default=True)

    # Identity
    polymer = fields.Selection([
        ("pp", "PP"),
        ("hdpe", "HDPE"),
        ("ldpe", "LDPE"),
        ("lldpe", "LLDPE"),
        ("pet", "PET"),
        ("ps", "PS"),
        ("abs", "ABS"),
        ("pvc", "PVC"),
        ("nylon", "Nylon"),
        ("other", "Other"),
    ], index=True, required=True)

    sub_grade = fields.Char()

    form = fields.Selection([
        ("bale", "Bale"),
        ("regrind", "Regrind"),
        ("flake", "Flake"),
        ("pellet", "Pellet"),
        ("rollstock", "Rollstock"),
        ("purge", "Purge"),
        ("lump", "Lump"),
        ("other", "Other"),
    ], index=True, required=True)

    # Source & Process
    source_type = fields.Selection([
        ("post_industrial", "Post Industrial"),
        ("post_consumer", "Post Consumer"),
        ("mixed", "Mixed"),
        ("unknown", "Unknown"),
    ])

    origin_process_type = fields.Selection([
        ("injection", "Injection"),
        ("extrusion", "Extrusion"),
        ("blow_mold", "Blow Mold"),
        ("thermoform", "Thermoform"),
        ("film", "Film"),
        ("mixed", "Mixed"),
        ("unknown", "Unknown"),
    ])

    previously_washed = fields.Boolean()
    previously_pelletized = fields.Boolean()

    # Quality
    melt_flow_index = fields.Float(index=True)
    density = fields.Float()
    moisture_percent = fields.Float()
    contamination_percent = fields.Float(index=True)
    contains_metal = fields.Boolean()
    contains_fr = fields.Boolean()

    # Volume
    avg_lot_size_lbs = fields.Float(index=True)
    min_lot_size_lbs = fields.Float()
    max_lot_size_lbs = fields.Float()
    monthly_volume_lbs = fields.Float(index=True)

    frequency = fields.Selection([
        ("one_time", "One Time"),
        ("weekly", "Weekly"),
        ("biweekly", "Biweekly"),
        ("monthly", "Monthly"),
        ("contract", "Contract"),
    ])

    # Packaging
    packaging_type = fields.Selection([
        ("gaylord", "Gaylord"),
        ("supersack", "Super Sack"),
        ("loose", "Loose"),
        ("palletized", "Palletized"),
        ("bulk_trailer", "Bulk Trailer"),
        ("other", "Other"),
    ])

    avg_truckloads_per_month = fields.Float()

    # Compliance
    food_grade = fields.Boolean()
    medical_grade = fields.Boolean()
    certification_notes = fields.Text()

    # AI Enrichment
    freeform_notes = fields.Text()

    @api.constrains("partner_id")
    def _check_partner_is_facility(self):
        for rec in self:
            if not rec.partner_id.parent_id:
                raise ValidationError("Material profiles can only attach to facility-level partners.")

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

    def _emit_material_packet(self):
        for rec in self:
            packet = {
                "partner_id": rec.partner_id.id,
                "polymer": rec.polymer,
                "form": rec.form,
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
                    "source_type": rec.source_type,
                    "origin_process": rec.origin_process_type,
                    "washed": rec.previously_washed,
                    "pelletized": rec.previously_pelletized,
                }
            }
            _ = packet

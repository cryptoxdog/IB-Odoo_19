from odoo import models, fields


class PlasticosBuyerCapability(models.Model):
    """Buyer Capability Lane — defines what a facility can accept.

    Each record represents one material lane: a combination of
    source_type + polymer + form + process_type that a buyer facility
    is willing and equipped to receive.  Quality, volume, and geo
    gates further constrain eligibility.
    """

    _name = "plasticos.buyer.capability"
    _description = "Buyer Capability (Facility Lane)"
    _order = "facility_id, polymer, form"
    _rec_name = "facility_id"

    active = fields.Boolean(default=True)

    facility_id = fields.Many2one(
        "plasticos.facility.profile",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # ── Identity gates (aligned with material.profile selections) ──

    source_type = fields.Selection(
        selection=[
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
        required=True,
        index=True,
    )

    polymer = fields.Selection(
        selection=[
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
        required=True,
        index=True,
    )

    form = fields.Selection(
        selection=[
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
        required=True,
        index=True,
    )

    process_type = fields.Selection(
        selection=[
            ("injection", "Injection Molding"),
            ("blow_mold", "Blow Molding"),
            ("extrusion", "Extrusion"),
            ("film_blown", "Film Blown"),
            ("film_cast", "Film Cast"),
            ("thermoform", "Thermoforming"),
            ("rotomold", "Rotational Molding"),
            ("compounding", "Compounding"),
            ("other", "Other"),
        ],
        string="Buyer Process Type",
        help="What the buyer DOES with the material (aligned to facility_profile.process_type).",
    )

    # ── Quality gates ────────────────────────────────────────

    max_contamination_pct = fields.Float(
        string="Max Contamination %",
        help="Reject intake if material contamination_percent exceeds this.",
    )
    max_moisture_pct = fields.Float(
        string="Max Moisture %",
        help="Reject intake if material moisture_percent exceeds this.",
    )

    # ── Commercial gates ─────────────────────────────────────

    min_volume_lbs = fields.Float(
        string="Min Volume (lbs)",
        help="Reject intake if quantity_per_load_lbs is below this.",
    )
    max_volume_lbs = fields.Float(
        string="Max Volume (lbs)",
        help="Reject intake if quantity_per_load_lbs exceeds this.",
    )

    # ── Compliance gates (boolean flags — no certification model) ──

    requires_food_grade = fields.Boolean(
        help="Reject intake if material is not food_grade.",
    )
    requires_medical_grade = fields.Boolean(
        help="Reject intake if material is not medical_grade.",
    )

    # ── Geo gate ─────────────────────────────────────────────

    radius_miles = fields.Float(
        string="Max Radius (miles)",
        help="Reject intake if seller is farther than this from buyer facility.",
    )

    _sql_constraints = [
        (
            "unique_lane",
            "unique(facility_id, source_type, polymer, form, process_type)",
            "Duplicate capability lane for this facility.",
        )
    ]

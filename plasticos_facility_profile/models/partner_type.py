from odoo import fields, models


class PlasticosPartnerType(models.Model):
    """Canonical partner/facility type master registry."""

    _name = "plasticos.partner.type"
    _description = "Partner Type Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. processor, broker, mrf).",
    )
    description = fields.Text(
        help="Detailed description of this partner type.",
    )
    is_facility = fields.Boolean(
        default=True,
        help="True if this type applies to facilities (companies with parent).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    # ── Gate Mode (for buyer matching v2.0) ────────────────────
    gate_mode = fields.Selection(
        [
            ("strict", "Strict"),
            ("flexible", "Flexible"),
            ("optimistic", "Optimistic"),
        ],
        default="flexible",
        help="Matching mode: strict=exact match required, flexible=partial match acceptable, optimistic=any match gets high score.",
    )

    _check_unique_code = models.Constraint(
        "unique(code)",
        "Partner type code must be unique.",
    )

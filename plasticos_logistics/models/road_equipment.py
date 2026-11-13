"""Domestic road equipment for a load (BRS-EXP-07-R002).

One Logistics catalog of the trailer a carrier brings for a domestic move:
53-foot trailer, 48-foot trailer, flatbed, and any other type an operator adds
as data. A flatbed is its own type with no assumed length. The actual move may
carry its own dimensions and restrictions on the load.

Nothing is inferred from the type: no payload, no weight limit, no VGM and no
container identity. An ISO container is a J1 journey, not a road equipment type,
and processing equipment at a facility is ``plasticos.equipment.type``. Export
references this catalog through the load and never keeps a second one.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosRoadEquipmentType(models.Model):
    _name = "plasticos.road.equipment.type"
    _description = "Plasticos Road Equipment Type"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True, help="Equipment the carrier brings, e.g. 53 ft Dry Van.")
    code = fields.Char(required=True, help="Stable code, e.g. trailer_53. Unique.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    nominal_length_ft = fields.Integer(
        string="Nominal Length (ft)",
        help="The length the type itself names. Empty when the type names none, as for a flatbed. "
        "No payload or weight limit is derived from it.",
    )
    description = fields.Text(help="What the type means for dispatch. Not a capacity rule.")

    _code_unique = models.Constraint("UNIQUE(code)", "A road equipment type with this code already exists.")
    _length_positive = models.Constraint(
        "CHECK(nominal_length_ft IS NULL OR nominal_length_ft > 0)",
        "A nominal length must be positive.",
    )

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if rec.code != rec.code.strip().lower() or " " in rec.code:
                raise ValidationError("A road equipment code is lowercase with no spaces, e.g. trailer_53.")

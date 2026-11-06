from odoo import models


class PlasticosMaterialProfileOrderLine(models.Model):
    """Purchase-line description owned by the module that defines the field."""

    _inherit = "plasticos.material.profile"

    def _purchase_line_description(self, po_line, line_vals):
        line = po_line.new(line_vals)
        return line.material_description or super()._purchase_line_description(po_line, line_vals)

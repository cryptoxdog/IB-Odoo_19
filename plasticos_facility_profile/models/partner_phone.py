from odoo import fields, models


class PlasticosPartnerPhone(models.Model):
    """A phone number besides the single number Odoo stores on the partner."""

    _name = "plasticos.partner.phone"
    _description = "Partner Phone"
    _order = "label, id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        required=True,
        ondelete="cascade",
        index=True,
    )
    label = fields.Selection(
        [("mobile", "Mobile"), ("other", "Other"), ("fax", "Fax")],
        string="Label",
        required=True,
    )
    number = fields.Char(string="Number", required=True)

    _unique_partner_phone = models.Constraint(
        "unique(partner_id, label, number)",
        "This phone number is already on the contact.",
    )

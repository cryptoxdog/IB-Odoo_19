from odoo import fields, models


class CrmLeadVanillaSoft(models.Model):
    """Extend crm.lead with VanillaSoft import tracking field."""

    _inherit = "crm.lead"

    vanillasoft_id = fields.Char(
        string="VanillaSoft Contact ID",
        index=True,
        copy=False,
        help="Original ContactID from VanillaSoft CRM. Used for deduplication during import.",
    )

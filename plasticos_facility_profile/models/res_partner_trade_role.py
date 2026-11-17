"""Trade role badge from the native ranks (ADR-131 Decision B).

``company_role`` stays the stored field it was; it is now computed from the
commercial partner's ``customer_rank`` / ``supplier_rank`` and stays writable,
so an explicit write still syncs the ranks (``_sync_rank_from_role``) and the
compute then shows the badge those ranks mean.
"""

from odoo import api, fields, models

from ..classification import trade_role


class ResPartner(models.Model):
    _inherit = "res.partner"

    company_role = fields.Selection(
        selection_add=[("both", "Both")],
        compute="_compute_company_role",
        store=True,
        readonly=False,
        help=(
            "Trade badge from the native ranks of the commercial partner: Buyer "
            "(customer rank), Supplier (supplier rank) or Both. Carrier, Broker, "
            "Internal, Prospect and Other stay only while neither rank is set."
        ),
    )

    _SUPPLIER_ROLES = {"supplier", "broker", "both"}
    _CUSTOMER_ROLES = {"buyer", "both"}

    @api.depends("commercial_partner_id.customer_rank", "commercial_partner_id.supplier_rank")
    def _compute_company_role(self):
        for partner in self:
            commercial = partner.commercial_partner_id or partner
            partner.company_role = trade_role(commercial.customer_rank, commercial.supplier_rank, partner.company_role)

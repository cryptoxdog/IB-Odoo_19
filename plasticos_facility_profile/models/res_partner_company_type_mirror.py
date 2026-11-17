"""Company Type tags mirror from a company onto its sites and people (ADR-131).

The one owner of the rule. When a company's tags change, each site and person
under it gets the company's Company Type tags; every other tag they carry (ERP
Contact Role, Status, ...) is left as it is. The writes it makes carry a context
key, so they do not mirror again.
"""

from odoo import Command, api, models

from ..classification import mirrored_tag_ids
from .res_partner_category import COMPANY_TYPE_XMLID

MIRROR_CONTEXT = "plasticos_company_type_mirror"


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _plasticos_mirror_company_type(self):
        if self.env.context.get(MIRROR_CONTEXT):
            return
        group = self.env.ref(COMPANY_TYPE_XMLID, raise_if_not_found=False)
        if not group:
            return
        member_ids = group.child_ids.ids
        quiet = self.with_context(**{MIRROR_CONTEXT: True})
        for company in self.filtered(lambda partner: partner.company_type == "company"):
            company_ids = company.category_id.ids
            children = quiet.search([("id", "child_of", company.id), ("id", "!=", company.id)])
            for child in children:
                current = set(child.category_id.ids)
                target = mirrored_tag_ids(current, company_ids, member_ids)
                if target != current:
                    child.write({"category_id": [Command.set(sorted(target))]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered("category_id")._plasticos_mirror_company_type()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "category_id" in vals:
            self._plasticos_mirror_company_type()
        return res

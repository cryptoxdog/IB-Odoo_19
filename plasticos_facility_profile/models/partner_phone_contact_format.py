"""Store every partner phone line in the same format as the partner's phone.

``mobile`` on ``res.partner`` is a projection of the ``mobile`` line, so this
also formats the mobile number. The line takes its partner's country, else the
partner's parent's, else US.
"""

from odoo import api, models

from ..services.contact_format import country_for, format_phone_result
from .res_partner_contact_format import log_contact_counters, new_counters

PARTNER_PHONE = "plasticos.partner.phone"
RES_PARTNER = "res.partner"


def _format_number(number, country_code, counters):
    result = format_phone_result(number, country_code)
    if not result.parsed and result.value:
        counters["unparseable"] += 1
    return result.value


class PlasticosPartnerPhoneContactFormat(models.Model):
    _inherit = PARTNER_PHONE

    @api.model
    def _plasticos_partner_country_code(self, partner):
        """The partner's country, else its commercial company's, else US."""
        return country_for(
            partner.country_id.code,
            partner.commercial_partner_id.country_id.code,
            partner.parent_id.commercial_partner_id.country_id.code,
        )

    @api.model_create_multi
    def create(self, vals_list):
        counters = new_counters()
        prepared = []
        for vals in vals_list:
            if isinstance(vals.get("number"), str):
                partner = self.env[RES_PARTNER].browse(vals.get("partner_id"))
                vals = dict(
                    vals, number=_format_number(vals["number"], self._plasticos_partner_country_code(partner), counters)
                )
            prepared.append(vals)
        log_contact_counters(counters, "plasticos.partner.phone create")
        return super().create(prepared)

    def write(self, vals):
        if not self or not isinstance(vals.get("number"), str):
            return super().write(vals)
        counters = new_counters()
        groups = {}
        for line in self:
            partner = self.env[RES_PARTNER].browse(vals["partner_id"]) if vals.get("partner_id") else line.partner_id
            groups.setdefault(self._plasticos_partner_country_code(partner), []).append(line.id)
        result = True
        for code, ids in groups.items():
            formatted = dict(vals, number=_format_number(vals["number"], code, counters))
            result = super(PlasticosPartnerPhoneContactFormat, self.browse(ids)).write(formatted) and result
        log_contact_counters(counters, "plasticos.partner.phone write")
        return result

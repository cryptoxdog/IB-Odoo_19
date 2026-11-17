"""Store every partner phone and email in one format, whatever wrote it.

The ERP import, the VanillaSoft import and a manual edit all reach the partner
through ``create`` / ``write``, so the values are formatted there, before the
row is written: no second write and no recursion. ``mobile`` is stored as a
``plasticos.partner.phone`` line and is formatted by that model.
"""

import logging

from odoo import api, models

from ..services.contact_format import country_for, format_emails_result, format_phone_result

_logger = logging.getLogger(__name__)

RES_PARTNER = "res.partner"
RES_COUNTRY = "res.country"
DEFAULT_COUNTRY = "US"


def format_contact_vals(vals, country_code, counters):
    """Return ``vals`` with ``phone`` / ``email`` formatted; count what was not understood."""
    formatted = dict(vals)
    phone = formatted.get("phone")
    if isinstance(phone, str):
        result = format_phone_result(phone, country_code)
        if not result.parsed and result.value:
            counters["unparseable"] += 1
        formatted["phone"] = result.value or False
    email = formatted.get("email")
    if isinstance(email, str):
        result = format_emails_result(email)
        counters["invalid_email_dropped"] += result.dropped
        formatted["email"] = result.value or False
    return formatted


def log_contact_counters(counters, origin):
    if counters["unparseable"] or counters["invalid_email_dropped"]:
        _logger.info(
            "%s: %d phone value(s) left unformatted (unparseable), %d malformed email entr(y/ies) dropped",
            origin,
            counters["unparseable"],
            counters["invalid_email_dropped"],
        )


def new_counters():
    return {"unparseable": 0, "invalid_email_dropped": 0}


class PlasticosResPartnerContactFormat(models.Model):
    _inherit = RES_PARTNER

    def _plasticos_contact_country_code(self):
        """The partner's country, else its commercial company's, else US (operator, 2026-11-17)."""
        self.ensure_one()
        return country_for(
            self.country_id.code,
            self.commercial_partner_id.country_id.code,
            self.parent_id.commercial_partner_id.country_id.code,
        )

    @api.model
    def _plasticos_country_code_from_vals(self, vals):
        country_id = vals.get("country_id")
        if country_id:
            return self.env[RES_COUNTRY].browse(country_id).code or DEFAULT_COUNTRY
        parent_id = vals.get("parent_id")
        if parent_id:
            parent = self.browse(parent_id)
            return country_for(parent.country_id.code, parent.commercial_partner_id.country_id.code)
        return DEFAULT_COUNTRY

    @api.model_create_multi
    def create(self, vals_list):
        counters = new_counters()
        prepared = []
        for vals in vals_list:
            if "phone" in vals or "email" in vals:
                vals = format_contact_vals(vals, self._plasticos_country_code_from_vals(vals), counters)
            prepared.append(vals)
        log_contact_counters(counters, "res.partner create")
        return super().create(prepared)

    def write(self, vals):
        if not self or ("phone" not in vals and "email" not in vals):
            return super().write(vals)
        counters = new_counters()
        # The same raw value may format differently per country, so group by it.
        groups = {}
        for partner in self:
            if vals.get("country_id"):
                code = self._plasticos_country_code_from_vals(vals)
            elif "country_id" in vals or "parent_id" in vals:
                parent = self.browse(vals["parent_id"]) if "parent_id" in vals else partner.parent_id
                own = partner.country_id.code if "country_id" not in vals else None
                code = country_for(own, parent.country_id.code, parent.commercial_partner_id.country_id.code)
            else:
                code = partner._plasticos_contact_country_code()
            groups.setdefault(code, []).append(partner.id)
        result = True
        for code, ids in groups.items():
            formatted = format_contact_vals(vals, code, counters)
            result = super(PlasticosResPartnerContactFormat, self.browse(ids)).write(formatted) and result
        log_contact_counters(counters, "res.partner write")
        return result

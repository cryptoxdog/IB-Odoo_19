"""Fill blank opportunity contact names and emails from the location's person.

A stored name or email is left as the broker, web lead, or VanillaSoft wrote it.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {"mail_notrack": True, "tracking_disable": True})
    leads = env["crm.lead"].search(
        [
            ("partner_id", "!=", False),
            ("partner_id.is_company", "=", True),
            "|",
            ("contact_name", "in", [False, ""]),
            ("email_from", "in", [False, ""]),
        ]
    )
    filled = 0
    for lead in leads:
        person = lead.partner_id._plasticos_reach_person()
        if not person:
            continue
        vals = {}
        if not (lead.contact_name or "").strip() and person.name:
            vals["contact_name"] = person.name
        if not (lead.email_from or "").strip() and person.email:
            vals["email_from"] = person.email
        if not vals:
            continue
        lead.write(vals)
        filled += 1
    _logger.info("Filled blank contact fields on %s opportunity(ies).", filled)

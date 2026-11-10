"""Fill pickup ZIP, seller location text, and Location on leads that already exist."""

from __future__ import annotations

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """SQL-fill location fields so an intake-created lead is not blocked by the write guard."""
    from odoo.addons.plasticos_web_leads.zip_place import resolve_payloads

    env = api.Environment(cr, SUPERUSER_ID, {})
    leads = env["plasticos.web.lead"].with_context(active_test=False).search([])
    for lead in leads:
        postal_code, location_text, location = resolve_payloads(lead.canonical_payload, lead.raw_payload)
        cr.execute(
            """
            UPDATE plasticos_web_lead
               SET pickup_postal_code = %s,
                   pickup_location_text = %s,
                   pickup_place = %s
             WHERE id = %s
            """,
            (postal_code or None, location_text or None, location or None, lead.id),
        )
    leads.invalidate_recordset(["pickup_postal_code", "pickup_location_text", "pickup_place"])
    _logger.info("plasticos_web_leads 19.0.2.9.0 post-migrate: location filled for %s leads", len(leads))

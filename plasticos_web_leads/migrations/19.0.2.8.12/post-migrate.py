"""Store the seller submission date, then replay stored evidence through classify_lead."""

from __future__ import annotations

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """SQL-fill submitted_at, then reclassify rows that have no intake."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    leads = env["plasticos.web.lead"].with_context(active_test=False).search([("submitted_at", "=", False)])
    for lead in leads:
        stamp = lead._submitted_at_from_payload(lead.raw_payload, lead.canonical_payload) or lead.create_date
        if not stamp:
            continue
        cr.execute(
            "UPDATE plasticos_web_lead SET submitted_at = %s WHERE id = %s AND submitted_at IS NULL",
            (stamp, lead.id),
        )
    leads.invalidate_recordset(["submitted_at"])
    env["plasticos.web.lead"]._reclassify_stored_leads()
    _logger.info("plasticos_web_leads 19.0.2.8.12 post-migrate: dates filled and stored evidence replayed")

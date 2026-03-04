"""Migrate lead_source_id from plasticos.lead.source to utm.source.

This migration runs when plasticos_facility_profile is upgraded to 19.0.4.0.0.
It maps old plasticos.lead.source records (by code) to new utm.source records (by name).
"""

import logging

_logger = logging.getLogger(__name__)

# Map old plasticos.lead.source codes → new utm.source names
CODE_TO_UTM_NAME = {
    "data_provider": "Data Provider",
    "enf": "ENF / Industry Database",
    "google": "Google Search",
    "association": "Industry Association",
    "internal": "Internal Research",
    "linkedin": "LinkedIn",
    "manta": "Manta Directory",
    "other": "Other",
    "pnews": "Plastics News",
    "recycle_net": "Recycle.net",
    "referral": "Referral",
    "siccode": "SICCODE",
    "state_list": "State Facility List",
    "thomasnet": "ThomasNet",
    "trade_show": "Trade Show",
    "web_lead": "Web Lead Form",
    "web_research": "Web Research",
}


def migrate(cr, version):
    """Migrate partner lead_source_id from plasticos.lead.source to utm.source."""
    if not version:
        return

    _logger.info("Starting lead_source_id migration: plasticos.lead.source → utm.source")

    # Check if old table exists (might already be removed)
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'plasticos_lead_source'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info("plasticos_lead_source table does not exist — skipping migration")
        return

    # Get all old lead sources
    cr.execute("SELECT id, code FROM plasticos_lead_source WHERE code IS NOT NULL")
    old_sources = dict(cr.fetchall())

    if not old_sources:
        _logger.info("No old lead sources found — skipping migration")
        return

    migrated = 0
    for old_id, old_code in old_sources.items():
        utm_name = CODE_TO_UTM_NAME.get(old_code)
        if not utm_name:
            _logger.warning("No UTM mapping for code '%s' (old ID %d)", old_code, old_id)
            continue

        # Find the new utm.source record
        cr.execute("SELECT id FROM utm_source WHERE name = %s LIMIT 1", (utm_name,))
        row = cr.fetchone()
        if not row:
            _logger.warning("utm.source '%s' not found for code '%s'", utm_name, old_code)
            continue

        new_id = row[0]

        # Update all partners pointing to the old lead_source_id
        cr.execute(
            """
            UPDATE res_partner
            SET lead_source_id = %s
            WHERE lead_source_id = %s
        """,
            (new_id, old_id),
        )
        count = cr.rowcount
        if count:
            migrated += count
            _logger.info("Migrated %d partners: %s (old %d) → %s (new %d)", count, old_code, old_id, utm_name, new_id)

        # Update all intakes pointing to the old lead_source_id
        cr.execute(
            """
            UPDATE plasticos_intake
            SET lead_source_id = %s
            WHERE lead_source_id = %s
        """,
            (new_id, old_id),
        )
        intake_count = cr.rowcount
        if intake_count:
            _logger.info("Migrated %d intakes: %s → %s", intake_count, old_code, utm_name)

    _logger.info("Lead source migration complete: %d partner records migrated", migrated)

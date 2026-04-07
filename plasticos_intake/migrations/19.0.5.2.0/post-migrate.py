import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill packaging_type_id (Many2one) from plasticos_intake_packaging_rel (Many2many).

    Version 19.0.5.2.0 changed packaging_type_ids (Many2many) to packaging_type_id
    (Many2one). The old relation table plasticos_intake_packaging_rel remains after
    the Odoo update. This migration copies the first packaging value per intake into
    the new column, preserving data for records that had a packaging selection.

    Idempotent: only touches rows where packaging_type_id IS NULL.
    """
    _logger.info(
        "[5.2.0 migration] Checking for old packaging relation table..."
    )

    # Guard: relation table may not exist on fresh installs
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'plasticos_intake_packaging_rel'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info(
            "[5.2.0 migration] plasticos_intake_packaging_rel not found — "
            "fresh install, skipping backfill"
        )
        return

    _logger.info(
        "[5.2.0 migration] Backfilling packaging_type_id from "
        "plasticos_intake_packaging_rel (taking MIN per intake)"
    )

    cr.execute("""
        UPDATE plasticos_intake pi
        SET packaging_type_id = rel.packaging_type_id
        FROM (
            SELECT DISTINCT ON (intake_id) intake_id, packaging_type_id
            FROM plasticos_intake_packaging_rel
            ORDER BY intake_id, packaging_type_id
        ) rel
        WHERE pi.id = rel.intake_id
          AND pi.packaging_type_id IS NULL
    """)

    cr.execute(
        "SELECT COUNT(*) FROM plasticos_intake WHERE packaging_type_id IS NOT NULL"
    )
    total = cr.fetchone()[0]
    _logger.info(
        "[5.2.0 migration] packaging_type_id backfill complete: %d intakes populated",
        total,
    )

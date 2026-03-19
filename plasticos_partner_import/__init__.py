from . import models
from . import wizards


def pre_init_hook(cr):
    """Clean up dependent records before partner XML ID cleanup.

    GUARDED: Only runs when PLASTICOS_PARTNER_WIPE=1 env var is set.
    This is a staging-only rebuild tool, NEVER runs in production.

    During module update, Odoo's _process_end() tries to delete partners
    whose XML IDs were removed. This fails if sale_order or other tables
    still reference those partners. This hook cleans up those references first.
    """
    import logging
    import os

    _logger = logging.getLogger(__name__)

    if os.environ.get("PLASTICOS_PARTNER_WIPE") != "1":
        _logger.info("pre_init_hook: Skipping cleanup (PLASTICOS_PARTNER_WIPE not set)")
        return

    _logger.warning("pre_init_hook: PLASTICOS_PARTNER_WIPE=1 — wiping all business records")

    # Delete sale orders (they reference partners via partner_id, partner_invoice_id, partner_shipping_id)
    cr.execute("SELECT COUNT(*) FROM sale_order")
    so_count = cr.fetchone()[0]
    if so_count:
        cr.execute("DELETE FROM sale_order_line")
        cr.execute("DELETE FROM sale_order")
        _logger.info("Deleted %d sale orders and their lines", so_count)

    # Delete purchase orders (they reference partners via partner_id)
    cr.execute("SELECT COUNT(*) FROM purchase_order")
    po_count = cr.fetchone()[0]
    if po_count:
        cr.execute("DELETE FROM purchase_order_line")
        cr.execute("DELETE FROM purchase_order")
        _logger.info("Deleted %d purchase orders and their lines", po_count)

    # Delete stock pickings (they reference partners)
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'stock_picking'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT COUNT(*) FROM stock_picking")
        pick_count = cr.fetchone()[0]
        if pick_count:
            cr.execute("DELETE FROM stock_move_line")
            cr.execute("DELETE FROM stock_move")
            cr.execute("DELETE FROM stock_picking")
            _logger.info("Deleted %d stock pickings", pick_count)

    # Delete account moves (invoices/bills reference partners)
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'account_move'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT COUNT(*) FROM account_move WHERE state = 'draft'")
        draft_count = cr.fetchone()[0]
        if draft_count:
            cr.execute(
                "DELETE FROM account_move_line WHERE move_id IN (SELECT id FROM account_move WHERE state = 'draft')"
            )
            cr.execute("DELETE FROM account_move WHERE state = 'draft'")
            _logger.info("Deleted %d draft account moves", draft_count)

    # Delete plasticos transactions (they reference partners)
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'plasticos_transaction'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT COUNT(*) FROM plasticos_transaction")
        tx_count = cr.fetchone()[0]
        if tx_count:
            cr.execute("DELETE FROM plasticos_transaction_line")
            cr.execute("DELETE FROM plasticos_transaction")
            _logger.info("Deleted %d plasticos transactions", tx_count)

    # Delete plasticos intakes (they reference partners)
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'plasticos_intake'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT COUNT(*) FROM plasticos_intake")
        intake_count = cr.fetchone()[0]
        if intake_count:
            cr.execute("DELETE FROM plasticos_intake")
            _logger.info("Deleted %d plasticos intakes", intake_count)

    # Delete plasticos loads (they reference partners)
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = 'plasticos_load'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT COUNT(*) FROM plasticos_load")
        load_count = cr.fetchone()[0]
        if load_count:
            cr.execute("DELETE FROM plasticos_load")
            _logger.info("Deleted %d plasticos loads", load_count)

    _logger.info("pre_init_hook: Cleanup complete")


def post_init_hook(env):
    """Auto-import partners from CSV on first module install."""
    import logging
    import os

    _logger = logging.getLogger(__name__)

    # Check if partners already imported (look for external ID marker)
    marker = env.ref("plasticos_partner_import.auto_import_complete", raise_if_not_found=False)
    if marker:
        _logger.info("Partner auto-import already completed, skipping")
        return

    module_path = os.path.dirname(os.path.abspath(__file__))
    corporate_csv = os.path.join(module_path, "1. Counterparties - Parent - CORPORATE-Ready To Import.csv")
    facility_csv = os.path.join(module_path, "2. Counterparties - Child - FACILITY LOCATIONS.csv")

    if not os.path.exists(corporate_csv) or not os.path.exists(facility_csv):
        _logger.warning("Partner CSV files not found, skipping auto-import")
        return

    _logger.info("Starting automatic partner import from CSV files...")

    try:
        service = env["plasticos.partner.import.service"]
        result = service.run_csv_import(corporate_csv, facility_csv)
        _logger.info("Auto-import complete: %s", result)

        # Create marker to prevent re-import
        env["ir.model.data"].create(
            {
                "name": "auto_import_complete",
                "module": "plasticos_partner_import",
                "model": "ir.model.data",
                "res_id": 1,  # Dummy reference
                "noupdate": True,
            }
        )
        env.cr.commit()

    except Exception as e:
        _logger.error("Partner auto-import failed: %s", e)
        # Don't raise - allow module install to continue

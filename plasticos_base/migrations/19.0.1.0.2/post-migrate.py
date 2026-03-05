import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Run filestore orphan cleanup immediately after update."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Starting immediate cleanup of missing filestore orphans...")
    try:
        # Run cleanup (will delete rows pointing to missing files)
        count = env["ir.attachment"]._cron_cleanup_missing_filestore_orphans()
        _logger.info(f"Finished cleanup: {count} orphans removed.")
    except Exception as e:
        _logger.error(f"Failed to cleanup missing filestore orphans: {e}")

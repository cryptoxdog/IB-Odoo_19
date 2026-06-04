"""Clean up plasticos.commission.config table and ACL leftovers.

The model was converted from models.Model → AbstractModel (no table).
Drop the orphaned table and ACL records so autovacuum stops crashing.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Approved one-time cleanup: model is now AbstractModel with no table.
    # nosemgrep: plasticos-destructive-migration-sql-py
    cr.execute("DROP TABLE IF EXISTS plasticos_commission_config CASCADE")
    _logger.info("Dropped orphaned table plasticos_commission_config (if it existed)")

    cr.execute(
        """
        DELETE FROM ir_model_access
        WHERE id IN (
            SELECT a.id
            FROM ir_model_access a
            JOIN ir_model_data d ON d.res_id = a.id AND d.model = 'ir.model.access'
            WHERE d.name IN (
                'access_commission_config_user',
                'access_commission_config_manager'
            )
            AND d.module = 'plasticos_commission'
        )
        """
    )

    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'plasticos_commission'
        AND name IN (
            'access_commission_config_user',
            'access_commission_config_manager'
        )
        """
    )

    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'plasticos_commission'
        AND model = 'ir.model'
        AND name = 'model_plasticos_commission_config'
        """
    )

    _logger.info("Cleaned up commission_config ACL and model data records")

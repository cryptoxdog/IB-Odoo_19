import logging
import re

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove stale currency_provider field references from res.config.settings views.

    currency_provider is defined by the Enterprise module currency_rate_live.
    When that module is installed but its model layer is not fully loaded (e.g. partial
    upgrade, broken install state), the view XML still references the field but
    res.config.settings does not expose it — crashing Owl with "field is undefined".

    This migration strips the orphaned <label> and <field> nodes from any settings view
    that references currency_provider, making the Settings page load again.
    It is a no-op if currency_provider is not referenced in any view.
    """
    cr.execute(
        """
        SELECT id, name, arch_db
        FROM ir_ui_view
        WHERE model = 'res.config.settings'
          AND arch_db LIKE '%currency_provider%'
        """
    )
    rows = cr.fetchall()

    if not rows:
        _logger.info("plasticos_accounting migrate: no views reference currency_provider — nothing to do")
        return

    for view_id, view_name, arch in rows:
        original = arch

        # Strip <label for="currency_provider" ... /> (self-closing)
        arch = re.sub(r'<label\b[^>]*\bfor=["\']currency_provider["\'][^>]*/>', "", arch)
        # Strip <field name="currency_provider" ... /> (self-closing)
        arch = re.sub(r'<field\b[^>]*\bname=["\']currency_provider["\'][^>]*/>', "", arch)
        # Strip now-empty <div class="row ..."> wrappers left behind
        arch = re.sub(r'<div\b[^>]*class=["\'][^"\']*row[^"\']*["\'][^>]*>\s*</div>', "", arch)

        if arch != original:
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                (arch, view_id),
            )
            _logger.info(
                "plasticos_accounting migrate: patched view '%s' (id=%s) — removed currency_provider references",
                view_name,
                view_id,
            )

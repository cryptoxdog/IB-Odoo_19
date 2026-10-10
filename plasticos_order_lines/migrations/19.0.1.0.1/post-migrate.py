import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Rebuild stored material projections so the product name leads."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model_name in ("sale.order.line", "purchase.order.line"):
        lines = env[model_name].search([])
        env.add_to_compute(lines._fields["material_description"], lines)
        _logger.info("Queued material projection recompute for %s %s lines", len(lines), model_name)
    env.flush_all()

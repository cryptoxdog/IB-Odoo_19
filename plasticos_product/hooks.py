"""Post-install hooks for plasticos_product module."""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Post-init hook: Auto-create products for all polymers.

    Called after module install/upgrade. Creates a product.template
    for each plasticos.polymer that doesn't already have one.
    """
    _logger.info("plasticos_product post_init_hook: Creating polymer products")

    Polymer = env["plasticos.polymer"]
    polymers_without_product = Polymer.search([("product_id", "=", False)])
    if polymers_without_product:
        polymers_without_product.action_create_products()
        _logger.info(
            "Created products for %d polymers",
            len(polymers_without_product),
        )
    else:
        _logger.info("All polymers already have products")

from . import models


def _post_init_create_polymer_products(env):
    """
    Post-init hook: Auto-create products for all polymers.

    Called after module install/upgrade. Creates a product.template
    for each plasticos.polymer that doesn't already have one.
    """
    Polymer = env["plasticos.polymer"]
    polymers_without_product = Polymer.search([("product_id", "=", False)])
    if polymers_without_product:
        polymers_without_product.action_create_products()

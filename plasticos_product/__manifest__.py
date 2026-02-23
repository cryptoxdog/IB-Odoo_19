{
    "name": "PlasticOS Product Catalog",
    "version": "19.0.1.0.1",
    "category": "Inventory/Product",
    "summary": "Scrap plastic product catalog with polymer-synced products",
    "description": """
PlasticOS Product Catalog
=========================
Defines the product catalog for scrap plastic trading operations.

Features:
- Auto-creates one product per polymer (1:1 sync)
- Products are thin wrappers; full material specs live on order lines
- Links products to polymer master records
    """,
    "author": "PlasticOS",
    "website": "https://plasticos.io",
    "license": "LGPL-3",
    "depends": [
        "product",
        "plasticos_material_profile",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/product_category_data.xml",
        "data/product_data.xml",
    ],
    "post_init_hook": "_post_init_create_polymer_products",
    "installable": True,
    "auto_install": False,
    "application": False,
}

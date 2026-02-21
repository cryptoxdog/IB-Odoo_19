{
    "name": "PlasticOS Product Catalog",
    "version": "19.0.1.0.0",
    "category": "Inventory/Product",
    "summary": "Scrap plastic product catalog with material attributes",
    "description": """
PlasticOS Product Catalog
=========================
Defines the product catalog for scrap plastic trading operations.

Features:
- 96 pre-defined scrap plastic products
- Links products to material profile attributes (polymer, form, color, source type)
- Product categories for organization
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
    "installable": True,
    "auto_install": False,
    "application": False,
}

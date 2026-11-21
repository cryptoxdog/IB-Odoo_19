{
    "name": "PlasticOS Order Lines",
    "version": "19.0.1.1.4",
    "category": "Inventory/Purchase",
    "summary": "Extend PO/SO lines with full material specifications",
    "description": """
PlasticOS Order Lines
=====================
Extends purchase.order.line and sale.order.line with material profile fields.

Each order line captures the full material specification:
- Polymer (from product)
- Material Grade
- Color
- Form
- Packaging Type
- Source Type
- Filler Type
- Material Attributes

Fields are pre-filled from material_profile_id but remain editable.
Computed full description: "HDPE Blue Regrind - Gaylords - Post-Industrial"
    """,
    "author": "Igor Beylin",
    "website": "https://plasticos.io",
    "license": "Other proprietary",
    "depends": [
        "purchase",
        "sale",
        "sale_management",
        "plasticos_material_profile",
        "plasticos_product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "application": False,
}

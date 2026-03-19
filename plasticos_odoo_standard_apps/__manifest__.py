{
    "name": "PlasticOS — Standard Odoo Apps (auto)",
    "version": "19.0.1.0.0",
    "summary": (
        "Auto-installs Odoo CE apps matching the PlasticOS home dashboard "
        "(Discuss, Calendar, Contacts, CRM, Sales, Dashboards, Accounting, "
        "Purchase, Inventory, Barcode basics)."
    ),
    "category": "Hidden",
    "author": "PlasticOS",
    "license": "LGPL-3",
    # Native apps visible on home (excluding PlastOS tiles, Apps, Settings).
    # Mapping: Discuss→mail, Dashboards→spreadsheet_dashboard, Barcode→barcodes.
    # Enterprise-only (AI, Inventory Barcode app): see README.rst — add to depends on Odoo.sh if needed.
    "depends": [
        "base",
        "base_setup",
        "web",
        "mail",
        "calendar",
        "contacts",
        "crm",
        "sale_management",
        "spreadsheet_dashboard",
        "account",
        "purchase",
        "stock",
        "barcodes",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": ["base"],
}

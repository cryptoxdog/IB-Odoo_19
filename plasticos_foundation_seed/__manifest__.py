{
    "name": "Plasticos Foundation Seed",
    "version": "19.0.1.1.0",
    "summary": "Deterministic XML seed module (Odoo 19)",
    "author": "Scrap Management Inc",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "account",
        "sale_management"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/reference_types_data.xml",
        "data/partner_tags.xml",
        "data/payment_terms.xml",
        "data/incoterms.xml",
        "data/sales_reps.xml",
        "data/accounts.xml",
        "data/material_taxonomy.xml"
    ],
    "installable": True,
    "application": False
}

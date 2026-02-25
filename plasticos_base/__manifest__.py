{
    "name": "PlasticOS Base",
    "version": "19.0.1.0.0",
    "summary": "Core seed data: partner tags, sales reps, material taxonomy tags",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Hidden",
    "depends": [
        "base",
        "contacts",
        "sale_management",
    ],
    "data": [
        "data/partner_tags.xml",
        "data/material_taxonomy.xml",
        "data/sales_reps.xml",
        "data/attachment_maintenance_cron.xml",
    ],
    "installable": True,
    "application": False,
}

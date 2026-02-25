{
    "name": "PlasticOS Base",
    "version": "19.0.1.0.1",
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
        "data/service_user.xml",
        "data/partner_tags.xml",
        "data/material_taxonomy.xml",
        "data/sales_reps.xml",
        "data/attachment_maintenance_cron.xml",
        "data/midnight_recompute_cron.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

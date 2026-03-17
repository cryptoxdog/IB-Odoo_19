{
    "name": "Plasticos Intake Normalizer",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "Schema-driven intake normalization — validates, assembles, and stores L9-ready packets.",
    "author": "Plasticos IB",
    "depends": [
        "plasticos_intake",
        "plasticos_material_profile",
        "plasticos_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/normalizer_config_data.xml",
        "data/cron_batch_normalize.xml",
        "views/normalizer_config_views.xml",
        "views/intake_normalizer_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": True,
    "license": "LGPL-3",
}

{
    "name": "Plasticos Intake Normalizer",
    "version": "19.0.1.0.0",
    "category": "Operations",
    "summary": "Schema-driven intake normalization — validates, assembles, and stores L9-ready packets.",
    "author": "Plasticos IB",
    "depends": [
        "plasticos_intake",
        "plasticos_foundation_seed",
        "plasticos_material_profile",
    ],
    "data": [
        "data/normalizer_config_data.xml",
        "data/cron_batch_normalize.xml",
        "security/ir.model.access.csv",
        "views/normalizer_config_views.xml",
        "views/intake_normalizer_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}

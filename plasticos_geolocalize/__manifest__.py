{
    "name": "PlasticOS Geolocalize",
    "version": "19.0.1.0.0",
    "summary": "Auto-geocode partners on create/write + nightly backfill cron",
    "author": "PlasticOS",
    "depends": [
        "plasticos_base",
        "base",
        "base_geolocalize",
        "plasticos_intake",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_geo_backfill.xml",
        "views/intake_geo_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": ["plasticos_base"],
    "application": False,
    "license": "LGPL-3",
}
